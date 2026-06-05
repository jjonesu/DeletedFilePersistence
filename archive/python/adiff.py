#!/usr/bin/env python3
#
# adiff.py:
# record sector content changes for deleted files in
# sequential disk snapshots
#
# 10/6-26/15: (jhj) original coding...
# 11/04/15: (jhj) removed idifference summary flag - was crashing on M57-pat
# 11/10/15: (jhj) fixed DFXML parser bug (added handling for continuation byte_run(s)
# 02/29/16: (jhj) misc cleanup
# 04/06/16: (jhj) fixed bug (added 'byte_run_' exclusion)
# 04/28/16: (jhj) added deleted.db creation and cleaning code
# 05/04/16: (jhj) add resident/nonresident parsing and db entry;
#                 add frag counter parsing and db entry;
#                 add progress counters
# 06/06/16: (jhj) fixed temp.dfxml parsing bug: some entries have two data blocks, so
#                     look for original_fileobject tag before processing

# for debugging
#import pdb
#pdb.set_trace()
#

import os
import sys
import hashlib
import sqlite3
import binascii
from datetime import datetime

### User-set vars...
IDIFF2_PATH='/path_to/dfxml/python/idifference2.py'
SECTOR_SIZE=512 # 512,4096,... use image drive sector size
IMAGE_LIST=['image0.img','image1.img',...] # python list of image files; order matters
HAVE_TEMP_DFXML=True # True if you already have a temp.dfxml file (idiff output for images 1-2), otherwise False; saves time
### end User-set vars

def find_deleted(i1,i2):
    # find deleted files using idiff then parsing dfxml outfile
    ### run idiff, write output to temp file - note that we are not catching errors from idifference2.py... (we should)
    if (HAVE_TEMP_DFXML == False): # if you already have a temp.dfxml file, set above to True to skip this (slow) step
        cmd='python3 '+IDIFF2_PATH+' -x temp.dfxml '+i1+' '+i2
        print('Running: '+cmd)
        os.system(cmd)
    ### parse dfxml for deleted files and byte runs; put into sqlite db
    # FYI, db schema:
    #   CREATE TABLE deleted_files(
    #     img TEXT,
    #     filename TEXT,
    #     resident BOOLEAN,
    #     offset INTEGER,
    #     frags INTEGER,
    #     md5 TEXT);
    # open db
    conn_c = sqlite3.connect("deleted.db")
    c = conn_c.cursor()
    # crude (but fast?) method follows; comment out if better method is implemented (XTREE?)
    counter = 0
    img = i1 # set image identifier
    f_img = open(i1,'rb') # open image file for subsequent sector hashing
    with open('temp.dfxml','r') as fi:
        print('Processing files in temp.dfxml (NOTE: 0 size files are counted but not loaded into DB):')
        for line in fi:
            if 'delta:deleted_file="1"' in line: # process a deleted file line (one element in the DFXML file)
                counter+=1 # this and next line to show processing progress
                print(str(counter)+'\r',end="")
                if('type="resident"' in line):
                    resident = True
                else:
                    resident = False
                frags=0 # initialize
                ready_to_parse = False
                for item in line.split("<"):
                    if 'delta:original_fileobject' in item:
                        ready_to_parse = True
                        continue
                    if ready_to_parse:
                        if ('img_offset="' in item):
                            frags+=1
                        if ("filename>" in item) and ("/filename" not in item):
                            filename = item [ len("filename>") : ]
                        if ("byte_run" in item) and ("byte_runs" not in item) and ("byte_run_" not in item): # won't write to DB if no byte_run (prob size=0)
                            item_values = item.split('"')
                            if (item_values[2] == ' fill=') and (item_values[3] == '0'): # byte_run of all zeros not worth tracking
                                break # breaks out of the "for item" loop
                            if ((item_values[0] == 'byte_run file_offset=') and (item_values[2] == ' uncompressed_len=')): # continuation byte_run
                                file_offset = int(item_values[1])
                                offset = saved_img_offset + file_offset
                                length = int(item_values[3])
                            else:
                                offset = int(item_values[5]) # "img_offset" value in the DFXML file
                                length = int(item_values[7]) # "uncompressed_len" value in the DFXML file
                                saved_img_offset = offset # save the base offset for continuation byte_run(s)
                            md5 = compute_sector_md5(f_img,offset) # params are an open file handle and offset in bytes
                            insert_values = (img,filename,resident,offset,frags,md5)
                            c.execute('INSERT into deleted_files VALUES (?,?,?,?,?,?)', insert_values)
                            length = length - SECTOR_SIZE # will be greater than 0 if more than one sector in this byte run
                            while length > 0:
                                offset = offset+SECTOR_SIZE
                                md5 = compute_sector_md5(f_img,offset)
                                insert_values = (img,filename,resident,offset,frags,md5)
                                c.execute('INSERT into deleted_files VALUES (?,?,?,?,?,?)', insert_values)
                                length = length - SECTOR_SIZE # will still be greater than 0 if more sectors in this byte run
    # close db and img file
    conn_c.commit()
    conn_c.close()
    f_img.close()
    print('\n')

def compute_sector_md5(fh,offset):
    fh.seek(offset) # seek takes bytes
    sector_contents = fh.read(SECTOR_SIZE) # assumes read returns binary (bytes object)
    r = hashlib.md5(sector_contents).digest()
    r_string = (str(binascii.b2a_hex(r)))[2:-1]
    return r_string

def hash_subsequent(img):
    print('Processing: '+img)
    counter = 0
    print('Processing sectors in deleted.db:')
    # hash sectors from base image deleted files as they exist in subsequent images
    f_img = open(img,'rb') # open image file for subsequent sector hashing
    conn_c = sqlite3.connect("deleted.db")
    c = conn_c.cursor()
    query="SELECT filename,resident,offset,frags from deleted_files where img=\""+IMAGE_LIST[0]+"\";" # get rows from first (base) image only
    c.execute(query)
    for row in c.fetchall():
        counter+=1
        print(str(counter)+'\r',end="")
        filename,resident,offset,frags = row
        md5 = compute_sector_md5(f_img,offset)
        insert_values = (img,filename,resident,offset,frags,md5)
        c.execute('INSERT into deleted_files VALUES (?,?,?,?,?,?)', insert_values)
    conn_c.commit()
    conn_c.close()
    f_img.close()
    print('\n')

if __name__ == "__main__":
    # run: python3 adiff.py &>console.log
    # need better option handling, help/usage
    print('Start: '+str(datetime.now()))
    # create or clean deleted.db as necessary
    if not (os.path.isfile('deleted.db')): # create db file if it does not exist
        #cmd='sqlite3 deleted.db < create_deleted.sql'
        cmd='sqlite3 deleted.db "CREATE TABLE deleted_files(img TEXT, filename TEXT, resident BOOLEAN, offset INTEGER, frags INTEGER, md5 TEXT);"'
        print('Running: '+cmd)
        os.system(cmd)
    else: # empty the db file if it does exist
        cmd='sqlite3 deleted.db "DELETE from deleted_files;"'
        print('Running: '+cmd)
        os.system(cmd)
    find_deleted(IMAGE_LIST[0],IMAGE_LIST[1])
    for i in range(1,len(IMAGE_LIST)): # hash sectors in other images and store in DB
        hash_subsequent(IMAGE_LIST[i])
    print('Stop: '+str(datetime.now()))

