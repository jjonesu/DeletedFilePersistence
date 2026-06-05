#!/usr/bin/env python3
#
# trace_file.py:
# This file processes a sqlite3 db of tracked files and sectors for output (viz, etc.) such as created by adiff.py
#
# NOTES:
# 02-15-16: jhj: initial code
# 02-19-16: jhj: interim release
# 02-25-16: jhj: added plot calcs
# 02-29-16: jhj: use flags to control output
# 03-18-16: jhj: added total sectors to graphs
# 05-04-16: jhj: added final persistence as % and n/m to plots;
#                added graph data output to file
# 05-05-16: jhj  added progress counters
# 06-06-16: jhj  added option to write processed data to csv file (for WEKA, etc.)
# 06-24-16: jhj  fixed resident translation bug (boolean to string)
# 06-25-16: jhj  really fixed resident translation bug (boolean to string) - sql "LIKE" was returning too many hits, resident was OK
#                also fixed repeated writes to csv for each frag value (now do a secondary query for max(frags)

# for debugging
#import pdb
#pdb.set_trace()
#

import os
import sqlite3
import numpy as np
import matplotlib
matplotlib.use('pdf')
import matplotlib.pyplot as plt

# Globals
DB = 'deleted.db' # DB to use
DBT = 'deleted_files' # DB table to use
NUM_IMAGES = 13 # number of images originally processed
SECTOR_SIZE = 512 # sector size of imaged media filesystem
# Flags (ToDo: set by CLI flags)
CREATE_GRAPHS = True # plots line graphs of persistence as PDF files; written to ./plots/filename.pdf
WRITE_FILE = True # writes graph data to a file (graphdata.out)
PLOT_ALL_ON_ONE = True # plots all lines on one graph; dense but interesting; otherwise one plot per file
OUTPUT_CHANGES_BY_IMAGE = False # outputs persistence (* and .) for each sector across the images
OUTPUT_FINAL_PERSISTENCE = True # output final % persistence
CREATE_PROCESSED_CSV = True # write processed file data to a sqlite3 db file for subsequent analysis

def compute_num_sectors(filename):
        ''' computes number of sectors being tracked for a file
        '''
        conn_c = sqlite3.connect(DB)
        c = conn_c.cursor()
        #query = "SELECT COUNT(DISTINCT offset) from "+DBT+" WHERE filename LIKE '%"+filename+"%';"
        query = "SELECT COUNT(DISTINCT offset) from "+DBT+" WHERE filename='"+filename+"';"
        c.execute(query)
        total_sectors=(c.fetchone())[0]
        conn_c.close()
        return total_sectors

def compute_changes(filename):
        ''' computes changes to sectors of a file and returns list with data
        '''
        counter = 0 # for progress counter
        print('Processing sectors in DB (total_sectors * NUM_IMAGES):')
        changes=[]
        conn_c = sqlite3.connect(DB)
        c = conn_c.cursor()
        #query = "SELECT offset,md5 FROM "+DBT+" WHERE filename LIKE '%"+filename+"%' ORDER BY offset;"
        query = "SELECT offset,md5 FROM "+DBT+" WHERE filename='"+filename+"' ORDER BY offset;"
        img = 0 # initialize image counter
        for row in c.execute(query):
                counter+=1
                print(str(counter)+'\r',end="")
                offset = row[0]
                md5 = row[1]
                if(img==0): # first image in the series
                        initial_md5 = md5
                        changed = 0 # value 0 means no change; non-0 indicates image where change first found
                        img+=1
                elif(img==(NUM_IMAGES-1)): # last image in the series
                        if(changed!=0): # already recorded change, so write, reset, and continue
                                changes.append((offset,changed))
                                img=0
                        else:
                                if(md5!=initial_md5):
                                        changed=img # set changed value to current image
                                changes.append((offset,changed))
                                img=0
                else: # neither first nor last image in the series
                        if(changed!=0): # already recorded change, so increment and continue
                                img+=1
                        else:
                                if(md5!=initial_md5):
                                        changed=img # set changed value to current image
                                img+=1
        print('\n')
        conn_c.close()
        return changes

def plot_persistence(filename,resident,frags,total_sectors,changes):
        ''' Computes % intact and plots simple line graph
        '''
        # compute survived at each image
        R = [] # list of number unchanged, i.e., Remaining, at each image
        for i in range (0,NUM_IMAGES): # init list with 0 counts
                R.append(0)
        L = [] # list of number changed, i.e., Lost, at each image
        for i in range (0,NUM_IMAGES): # init list with 0 counts
                L.append(0)
        for j in [x[1] for x in changes]: # http://stackoverflow.com/questions/
                                          # 3308102/how-to-extract-the-n-th-elements-from-a-list-of-tuples-in-python
                L[j]+=1
        # compute values to plot
        P = [] # list of % survived at each image
        for i in range (0,NUM_IMAGES): # init list with 0 values
                P.append(0)
        P[0] = float((total_sectors/total_sectors)*100.0) # all sectors always persist in image 0
        R[0] = total_sectors # all sectors always persist in image 0
        sectors_remaining = total_sectors # starting point
        for k in range (1,NUM_IMAGES): # compute % sectors remaining
                P[k] = float(((sectors_remaining - L[k])/total_sectors)*100.0)
                R[k] = sectors_remaining - L[k]
                sectors_remaining -= L[k] # running total of sectors remaining
        # plot
        if(CREATE_GRAPHS):
                # create plots directory if it does not exist
                if not os.path.exists('./plots/'):
                    os.makedirs('./plots/')
                fn = (filename.split('/'))[-1]
                x = range (0,NUM_IMAGES)
                y = P
                plt.plot(x,y,marker='.',markersize=8)
                # ToDo: restrict x-axis to integers...
                if(PLOT_ALL_ON_ONE): # different title and don't clear the figure between plots
                        plt.title('Deleted File Sector Persistence: All Files', size = 10)
                        plt.ylim(ymin = -1.0, ymax = 101.0)
                        plt.ylabel('% Sectors Intact')
                        plt.xlabel('Image ID (sequential)')
                        plt.savefig('./plots/all.pdf')
                else: # different title and clear the figure between plots
                        fp = "{0:.2f}".format(P[NUM_IMAGES-1]) # create rounded string of final persistence
                        plt.title('Deleted File Sector Persistence: '+fn+' (final persistence: '+fp+'%  '+\
                            str(sectors_remaining)+'/'+str(total_sectors)+')\n'+filename, size = 8)
                        plt.ylim(ymin = -1.0, ymax = 101.0)
                        plt.ylabel('% Sectors Intact')
                        plt.xlabel('Image ID (sequential)')
                        plt.savefig('./plots/'+fn+'.pdf')
                        plt.clf()
        # write graph data to file
        if(WRITE_FILE):
                fo = open('graphdata.out','a') # opening for append, since created new file in main block
                #ext = os.path.splitext(filename)[1][1:].strip().lower()
                fo.write('FILENAME: '+filename+'\n')
                fo.write('TOTAL_SECTORS: '+str(total_sectors)+'\n')
                for k in range (0,NUM_IMAGES): 
                        fp = "{0:.2f}".format(P[k]) # create rounded string of persistence percent
                        fo.write('IMAGE (R/T %): '+str(k)+' ('+str(R[k])+'/'+str(total_sectors)+' '+str(fp)+'%)\n')
                fo.write('\n')
                fo.close()
        # write processed data to csv file
        if(CREATE_PROCESSED_CSV):
                ext = os.path.splitext(filename)[1][1:].strip().lower()
                total_bytes = total_sectors * SECTOR_SIZE
                fo = open('processed.csv','a') # opening for append, since created new file in main block
                fo.write(filename+','+ext+','+str(total_sectors)+','+str(total_bytes)+','+str(int(resident))+','+str(frags))
                for k in range (0,NUM_IMAGES): 
                        fo.write(','+str(R[k]))
                fo.write('\n')
                fo.close()
        return sectors_remaining

def show_changes_by_image(filename,total_sectors,changes):
        ''' Prints simple graphic showing sector-by-sector decay over images
            Intact: * and Changed: .
            Non-sequential sectors indicate by ---
        '''
        print('\n')
        last_offset = 0
        for item in changes:
                if(item[1]==0):
                        symbols = '*' * NUM_IMAGES
                else:
                        symbols = '*' * item[1] + '.' * (NUM_IMAGES - item[1])
                if(((item[0]-last_offset)!=SECTOR_SIZE) and (last_offset!=0)): # non-contiguous sectors
                        print('---')
                print(str(item[0])+':'+symbols)
                last_offset = item[0]
        print('\n')

if __name__ == "__main__":
        if(WRITE_FILE):
                fo = open('graphdata.out','w') # creates a new file in case it already exists
                fo.close() # could leave open and pass filehandle in, then close at end...faster?
        if(CREATE_PROCESSED_CSV):
                fo = open('processed.csv','w') # creates a new file with headers
                fo.write('filename,ext,total_sectors,total_bytes,resident,frags,persistence...\n') # headers
                fo.close() # could leave open and pass filehandle in, then close at end...faster?
        filename = input('Filename to process (null to list files in the DB, * to process all): ')
        if(filename==''): # list files in the DB
                counter = 0
                conn_c = sqlite3.connect(DB)
                c = conn_c.cursor()
                query = 'SELECT distinct filename FROM '+DBT+';'
                for row in c.execute(query):
                        print(row[0])
                        counter +=1
                print('\nTotal files: '+str(counter)+'\n')
                conn_c.close()
        elif(filename=='*'): # process all files in the DB
                conn_c = sqlite3.connect(DB)
                c = conn_c.cursor()
                d = conn_c.cursor()
                #query = 'SELECT distinct filename,resident,frags FROM '+DBT+';' # testing to select only max(frags) entry in DB...
                query = 'SELECT distinct filename FROM '+DBT+';'
                for row in c.execute(query):
                        current_filename = row[0]
                        query = "SELECT filename,resident,max(frags) FROM "+DBT+" WHERE filename='"+current_filename+"' LIMIT 1;"
                        for sub_row in d.execute(query):
                            resident = sub_row[1]
                            frags = sub_row[2]
                            total_sectors = compute_num_sectors(current_filename)
                            print('\nFilename: '+current_filename)
                            print('Total Sectors: '+str(total_sectors))
                            changes = compute_changes(current_filename)
                            if(OUTPUT_CHANGES_BY_IMAGE):
                                    show_changes_by_image(current_filename,total_sectors,changes) # disable when running all?
                            sectors_remaining = plot_persistence(current_filename,resident,frags,total_sectors,changes)
                            if(OUTPUT_FINAL_PERSISTENCE):
                                    final_persistence_percent = format((float(sectors_remaining/total_sectors)*100.0), '.2f')
                                    print('Final Persistence: '+str(final_persistence_percent)+ \
                                            '% ('+str(sectors_remaining)+'/'+str(total_sectors)+')\n')
                conn_c.close()
        else: # process one specific file from the DB
                conn_c = sqlite3.connect(DB)
                c = conn_c.cursor()
                #query = "SELECT DISTINCT filename,resident,frags FROM "+DBT+" WHERE filename LIKE '%"+filename+"%';"
                query = "SELECT DISTINCT filename,resident,frags FROM "+DBT+" WHERE filename='"+filename+"';"
                #query = "SELECT COUNT(DISTINCT offset) from "+DBT+" WHERE filename LIKE '%"+filename+"%';"
                for row in c.execute(query):
                        resident = row[1]
                        frags = row[2]
                total_sectors = compute_num_sectors(filename)
                print('\nFilename: '+filename)
                print('Total Sectors: '+str(total_sectors))
                changes = compute_changes(filename)
                if(OUTPUT_CHANGES_BY_IMAGE):
                        show_changes_by_image(filename,total_sectors,changes)
                sectors_remaining = plot_persistence(filename,resident,frags,total_sectors,changes)
                if(OUTPUT_FINAL_PERSISTENCE):
                        final_persistence_percent = format((float(sectors_remaining/total_sectors)*100.0), '.2f')
                        print('Final Persistence: '+str(final_persistence_percent)+ \
                                '% ('+str(sectors_remaining)+'/'+str(total_sectors)+')\n')


