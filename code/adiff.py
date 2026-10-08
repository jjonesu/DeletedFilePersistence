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
# 02/26/26: (jhj) added code in main to delete file deleted.db if already exists
# 3/1/26:  (jhj) rewrote XML parser to handle out of order object attributes;
#                added DB indices and other performance enhancements per Claude
# 5/28/26: (jhj) major speed improvements per Claude: batch inserts, bulk sector reads,
#                write PRAGMAs, DB creation via Python sqlite3 instead of shell
# 6/4/26:  (jhj) reverted sort (hurt on WSL/SSD); added img index; larger batch/cache;
#                hash_subsequent reads each unique offset once then inserts from cache

import os
import subprocess
import sys
import hashlib
import sqlite3
import binascii
from datetime import datetime
import xml.etree.ElementTree as ET
import configparser

# read config file
config = configparser.ConfigParser(inline_comment_prefixes=('#', ';'))
_config_path = 'config.ini'
if not os.path.isfile(_config_path):
    print('ERROR: config.ini not found in current directory: ' + os.getcwd())
    sys.exit(1)
config.read(_config_path)

# Namespaces used in the DFXML file
NS = {
    'dfxml': 'http://www.forensicswiki.org/wiki/Category:Digital_Forensics_XML',
    'delta': 'http://www.forensicswiki.org/wiki/Forensic_Disk_Differencing',
    'dc':    'http://purl.org/dc/elements/1.1/'
}

# set variables from configuration file
IDIFF2_PATH     = config['settings']['IDIFF2_PATH']
SECTOR_SIZE     = config.getint('settings', 'SECTOR_SIZE')
IMAGE_LIST      = [x.strip() for x in config['settings']['IMAGE_LIST'].split(',')]
HAVE_TEMP_DFXML = config.getboolean('settings', 'HAVE_TEMP_DFXML')

BATCH_SIZE = 50000  # rows per executemany batch

print('Size of IMAGE_LIST: ' + str(len(IMAGE_LIST)))

def set_write_pragmas(conn):
    ''' Apply PRAGMAs that speed up bulk writes. '''
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=OFF")
    conn.execute("PRAGMA cache_size=-131072")  # 128 MB cache
    conn.execute("PRAGMA temp_store=MEMORY")
    conn.execute("PRAGMA mmap_size=268435456") # 256 MB mmap

def hash_sector_data(data):
    ''' Return hex-string MD5 of raw bytes. '''
    return hashlib.md5(data).hexdigest()

def find_deleted(img1_path, img2_path):

    if not HAVE_TEMP_DFXML:
        print('Running idifference2.py... (output in idifference2.log)')
        with open('idifference2.log', 'w') as log:
            result = subprocess.run(
                [sys.executable, IDIFF2_PATH, '-x', 'temp.dfxml', img1_path, img2_path],
                stdout=log, stderr=subprocess.STDOUT)
        # show only non-INFO/WARNING lines, as before
        with open('idifference2.log') as log:
            filtered = [l.rstrip() for l in log
                        if not (l.startswith('WARNING:') or l.startswith('INFO:'))]
        if any(filtered):
            print('idifference2.py output:\n' + '\n'.join(l for l in filtered if l))
        if result.returncode != 0:
            print('ERROR: idifference2.py exited with code ' + str(result.returncode))
            sys.exit(1)
        if not os.path.isfile('temp.dfxml'):
            print('ERROR: temp.dfxml was not created by idifference2.py')
            sys.exit(1)

    tree = ET.parse('temp.dfxml')
    root = tree.getroot()

    source = root.find('dfxml:source', NS)
    img = source.findall('dfxml:image_filename', NS)[0].text

    conn = sqlite3.connect("deleted.db")
    set_write_pragmas(conn)
    c = conn.cursor()
    f_img = open(img1_path, 'rb')

    rows_batch = []

    for fileobj in root.iter('{http://www.forensicswiki.org/wiki/Category:Digital_Forensics_XML}fileobject'):

        deleted = fileobj.get('{http://www.forensicswiki.org/wiki/Forensic_Disk_Differencing}deleted_file')
        if deleted != '1':
            continue

        orig = fileobj.find('delta:original_fileobject', NS)
        source_obj = orig if orig is not None else fileobj

        fn_el = source_obj.find('dfxml:filename', NS)
        filename = fn_el.text if fn_el is not None else ''

        alloc_el = fileobj.find('dfxml:alloc', NS)
        resident = 1 if (alloc_el is not None and alloc_el.get('type') == 'resident') else 0

        byte_runs_el = source_obj.find('dfxml:byte_runs', NS)
        if byte_runs_el is None:
            continue

        byte_runs = byte_runs_el.findall('dfxml:byte_run', NS)
        frags = sum(1 for br in byte_runs if br.get('img_offset') is not None)
        if frags == 0:
            frags = len(byte_runs)

        saved_img_offset = None

        for byte_run in byte_runs:
            img_offset = byte_run.get('img_offset')
            length     = byte_run.get('len')
            fill       = byte_run.get('fill')

            if fill == '0':
                continue

            if img_offset is None:
                file_offset = byte_run.get('file_offset')
                if file_offset is not None and saved_img_offset is not None:
                    img_offset = saved_img_offset + int(file_offset)
                    length = byte_run.get('uncompressed_len', length)
                else:
                    continue
            else:
                img_offset = int(img_offset)
                saved_img_offset = img_offset

            if length is None:
                continue
            length = int(length)

            f_img.seek(img_offset)
            run_data = f_img.read(length)

            offset = img_offset
            pos = 0
            while pos + SECTOR_SIZE <= len(run_data):
                md5 = hash_sector_data(run_data[pos:pos + SECTOR_SIZE])
                rows_batch.append((img, filename, resident, offset, frags, md5))
                offset += SECTOR_SIZE
                pos    += SECTOR_SIZE
                if len(rows_batch) >= BATCH_SIZE:
                    c.executemany('INSERT INTO deleted_files VALUES (?,?,?,?,?,?)', rows_batch)
                    rows_batch = []

    if rows_batch:
        c.executemany('INSERT INTO deleted_files VALUES (?,?,?,?,?,?)', rows_batch)

    print('Creating indices...')
    conn.execute("CREATE INDEX IF NOT EXISTS idx_img ON deleted_files(img);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_filename ON deleted_files(filename);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_filename_offset ON deleted_files(filename, offset);")
    conn.commit()
    conn.close()
    f_img.close()

def hash_subsequent(img):
    print('Processing: ' + img)

    conn = sqlite3.connect("deleted.db")
    set_write_pragmas(conn)
    c = conn.cursor()

    # Fetch unique offsets only — each offset read once regardless of how many
    # files share it. With idx_img this is a fast indexed scan.
    c.execute(
        "SELECT DISTINCT offset FROM deleted_files WHERE img=?",
        (IMAGE_LIST[0],)
    )
    unique_offsets = [row[0] for row in c.fetchall()]
    n_unique = len(unique_offsets)
    print('Reading ' + str(n_unique) + ' unique offsets from ' + img + '...')

    # Hash each unique offset once
    f_img = open(img, 'rb')
    md5_by_offset = {}
    for i, offset in enumerate(unique_offsets):
        if i % 100000 == 0 and i > 0:
            print(str(i) + '/' + str(n_unique) + '\r', end="")
        f_img.seek(offset)
        md5_by_offset[offset] = hash_sector_data(f_img.read(SECTOR_SIZE))
    f_img.close()
    print('\nHashing complete. Building insert batch...')

    # Now fetch all rows and insert using cached md5s — pure CPU/DB, no more I/O
    c.execute(
        "SELECT filename, resident, offset, frags FROM deleted_files WHERE img=?",
        (IMAGE_LIST[0],)
    )
    all_rows = c.fetchall()
    total = len(all_rows)

    rows_batch = []
    counter = 0
    for filename, resident, offset, frags in all_rows:
        counter += 1
        rows_batch.append((img, filename, resident, offset, frags, md5_by_offset[offset]))
        if len(rows_batch) >= BATCH_SIZE:
            c.executemany('INSERT INTO deleted_files VALUES (?,?,?,?,?,?)', rows_batch)
            rows_batch = []

    if rows_batch:
        c.executemany('INSERT INTO deleted_files VALUES (?,?,?,?,?,?)', rows_batch)

    conn.commit()
    conn.close()
    print('Done: ' + str(counter) + ' rows (' + str(n_unique) + ' unique offsets)\n')

if __name__ == "__main__":
    start_time = datetime.now()
    print('Start: ' + str(start_time))

    if os.path.isfile('deleted.db'):
        print('Removing old deleted.db')
        os.remove('deleted.db')

    print('Creating deleted.db')
    conn = sqlite3.connect('deleted.db')
    conn.execute(
        "CREATE TABLE deleted_files("
        "img TEXT, filename TEXT, resident BOOLEAN, "
        "offset INTEGER, frags INTEGER, md5 TEXT);"
    )
    conn.commit()
    conn.close()

    find_deleted(IMAGE_LIST[0], IMAGE_LIST[1])
    for i in range(1, len(IMAGE_LIST)):
        hash_subsequent(IMAGE_LIST[i])

    stop_time = datetime.now()
    print('Stop: ' + str(stop_time))
    print('Elapsed: ' + str(stop_time - start_time))
