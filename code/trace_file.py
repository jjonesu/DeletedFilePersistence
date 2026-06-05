#!/usr/bin/env python3
#
# trace_file.py:
# This file processes a sqlite3 db of tracked files and sectors (such as created by adiff.py) for output (viz, etc.) 
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
# 03-01-26: jhj  rewrote to speed it up; edits suggested by Claude (gave it the code, asked to speed it up)
# 05-28-26: jhj  fixed graph output; integer only on X axis
# 06-02-26: jhj  major speed improvements per Claude: bulk DB load, img-order sort, eliminated per-file queries
# 06-05-26: jhj  added flags; flattened PDF outfile

# for debugging
#import pdb
#pdb.set_trace()
#

import os
import sqlite3
import collections
import numpy as np
import matplotlib
matplotlib.use('pdf')
import matplotlib.pyplot as plt
import argparse
import configparser
from datetime import datetime

# read configuration file
config = configparser.ConfigParser(inline_comment_prefixes=('#', ';'))
config.read('config.ini') # name of config file; must be in local directory

# set variables from configuration file
DB                       = config['settings']['DB']
DBT                      = config['settings']['DBT']
SECTOR_SIZE              = config.getint('settings', 'SECTOR_SIZE')
CREATE_GRAPHS            = config.getboolean('settings', 'CREATE_GRAPHS')
WRITE_FILE               = config.getboolean('settings', 'WRITE_FILE')
PLOT_ALL_ON_ONE          = config.getboolean('settings', 'PLOT_ALL_ON_ONE')
OUTPUT_CHANGES_BY_IMAGE  = config.getboolean('settings', 'OUTPUT_CHANGES_BY_IMAGE')
OUTPUT_FINAL_PERSISTENCE = config.getboolean('settings', 'OUTPUT_FINAL_PERSISTENCE')
CREATE_PROCESSED_CSV     = config.getboolean('settings', 'CREATE_PROCESSED_CSV')
IMAGE_LIST               = [x.strip() for x in config['settings']['IMAGE_LIST'].split(',')]
NUM_IMAGES               = len(IMAGE_LIST)

# Build a lookup: img path -> image index (0-based)
IMG_INDEX = {img: i for i, img in enumerate(IMAGE_LIST)}

def load_file_data(filename, conn):
    ''' Load data for a single named file from the DB (used for single-file mode). '''
    c = conn.cursor()
    c.execute(
        "SELECT img, resident, offset, frags, md5 FROM deleted_files WHERE filename=?",
        (filename,)
    )
    sectors = collections.defaultdict(lambda: [None] * NUM_IMAGES)
    resident = 0
    frags = 0
    for img, res, offset, f, md5 in c:
        img_idx = IMG_INDEX.get(img)
        if img_idx is not None:
            sectors[offset][img_idx] = md5
        resident = res
        if f > frags:
            frags = f
    return {'resident': resident, 'frags': frags, 'sectors': sectors}

def stream_all_files(conn):
    ''' Stream the entire table in one sequential scan ordered by filename, offset.
        Yields (filename, file_data) one file at a time — peak RAM is one file's data.
        Much faster than 30k individual queries, uses far less RAM than loading all at once.
    '''
    c = conn.cursor()
    c.execute(
        "SELECT img, filename, resident, offset, frags, md5 "
        "FROM deleted_files ORDER BY filename, offset"
    )
    current_filename = None
    sectors  = None
    resident = 0
    frags    = 0
    for img, filename, res, offset, f, md5 in c:
        if filename != current_filename:
            if current_filename is not None:
                yield current_filename, {'resident': resident, 'frags': frags, 'sectors': sectors}
            current_filename = filename
            sectors  = collections.defaultdict(lambda: [None] * NUM_IMAGES)
            resident = res
            frags    = f
        img_idx = IMG_INDEX.get(img)
        if img_idx is not None:
            sectors[offset][img_idx] = md5
        if f > frags:
            frags = f
    if current_filename is not None:
        yield current_filename, {'resident': resident, 'frags': frags, 'sectors': sectors}

def count_distinct_files(conn):
    ''' Count distinct filenames — cheap query for progress display. '''
    c = conn.cursor()
    c.execute("SELECT COUNT(DISTINCT filename) FROM deleted_files WHERE img=?", (IMAGE_LIST[0],))
    return c.fetchone()[0]

def count_matching_files(conn, pattern):
    ''' Count files matching a LIKE pattern. '''
    c = conn.cursor()
    c.execute("SELECT COUNT(DISTINCT filename) FROM deleted_files WHERE img=? AND filename LIKE ?",
              (IMAGE_LIST[0], pattern))
    return c.fetchone()[0]

def stream_matching_files(conn, pattern):
    ''' Stream files matching a LIKE pattern in one sequential scan. '''
    c = conn.cursor()
    c.execute(
        "SELECT img, filename, resident, offset, frags, md5 "
        "FROM deleted_files WHERE filename LIKE ? ORDER BY filename, offset",
        (pattern,)
    )
    current_filename = None
    sectors  = None
    resident = 0
    frags    = 0
    for img, filename, res, offset, f, md5 in c:
        if filename != current_filename:
            if current_filename is not None:
                yield current_filename, {'resident': resident, 'frags': frags, 'sectors': sectors}
            current_filename = filename
            sectors  = collections.defaultdict(lambda: [None] * NUM_IMAGES)
            resident = res
            frags    = f
        img_idx = IMG_INDEX.get(img)
        if img_idx is not None:
            sectors[offset][img_idx] = md5
        if f > frags:
            frags = f
    if current_filename is not None:
        yield current_filename, {'resident': resident, 'frags': frags, 'sectors': sectors}

def compute_changes_from_data(sectors):
    ''' Compute changes list from pre-loaded sector data.
        sectors: dict of offset -> [md5_img0, md5_img1, ...]
        Returns list of (offset, changed_at_image_index) same as before.
    '''
    changes = []
    for offset in sorted(sectors.keys()):
        md5s = sectors[offset]
        initial_md5 = md5s[0]
        changed = 0
        if initial_md5 is not None:
            for img_idx in range(1, NUM_IMAGES):
                if md5s[img_idx] is not None and md5s[img_idx] != initial_md5 and changed == 0:
                    changed = img_idx
        changes.append((offset, changed))
    return changes

def plot_persistence(filename, resident, frags, total_sectors, changes, fo_graph=None, fo_csv=None):
    ''' Computes % intact and plots simple line graph '''
    R = [0] * NUM_IMAGES  # Remaining count at each image
    L = [0] * NUM_IMAGES  # Lost count at each image
    for _, changed_at in changes:
        L[changed_at] += 1
    P = [0.0] * NUM_IMAGES  # % survived at each image
    P[0] = 100.0  # all sectors always persist in image 0
    R[0] = total_sectors
    sectors_remaining = total_sectors
    for k in range(1, NUM_IMAGES):
        sectors_remaining -= L[k]
        R[k] = sectors_remaining
        P[k] = float(sectors_remaining / total_sectors * 100.0)
    # plot
    if CREATE_GRAPHS:
        if not os.path.exists('./plots/'):
            os.makedirs('./plots/')
        fn = (filename.split('/'))[-1]
        x = range(0, NUM_IMAGES)
        plt.plot(x, P, marker='.', markersize=8, rasterized=True)
        if PLOT_ALL_ON_ONE:
            # Title/labels set here but savefig called only once after all files are plotted
            plt.title('Deleted File Sector Persistence: All Files', size=10)
            plt.ylim(ymin=-1.0, ymax=101.0)
            plt.ylabel('% Sectors Intact')
            plt.xlabel('Image ID (sequential)')
            plt.gca().xaxis.set_major_locator(matplotlib.ticker.MaxNLocator(integer=True))
            # savefig intentionally omitted here — called once in main after all files processed
        else:
            fp = "{0:.2f}".format(P[NUM_IMAGES-1])
            plt.title('Deleted File Sector Persistence: '+fn+' (final persistence: '+fp+'%  ' +
                      str(R[NUM_IMAGES-1])+'/'+str(total_sectors)+')\n'+filename, size=8)
            plt.ylim(ymin=-1.0, ymax=101.0)
            plt.ylabel('% Sectors Intact')
            plt.xlabel('Image ID (sequential)')
            plt.gca().xaxis.set_major_locator(matplotlib.ticker.MaxNLocator(integer=True))
            plt.savefig('./plots/'+fn+'.pdf', dpi=150)
            plt.clf()
            plt.close('all')  # free matplotlib memory after each individual plot
    # write graph data to file
    if WRITE_FILE and fo_graph:
        fo_graph.write('FILENAME: '+filename+'\n')
        fo_graph.write('TOTAL_SECTORS: '+str(total_sectors)+'\n')
        for k in range(0, NUM_IMAGES):
            fp = "{0:.2f}".format(P[k])
            fo_graph.write('IMAGE (R/T %): '+str(k)+' ('+str(R[k])+'/'+str(total_sectors)+' '+fp+'%)\n')
        fo_graph.write('\n')
    # write processed data to csv file
    if CREATE_PROCESSED_CSV and fo_csv:
        ext = os.path.splitext(filename)[1][1:].strip().lower()
        total_bytes = total_sectors * SECTOR_SIZE
        fo_csv.write(filename+','+ext+','+str(total_sectors)+','+str(total_bytes)+','+str(int(resident))+','+str(frags))
        for k in range(0, NUM_IMAGES):
            fo_csv.write(','+str(R[k]))
        fo_csv.write('\n')
    return R[NUM_IMAGES-1]  # sectors remaining at last image

def show_changes_by_image(filename, total_sectors, changes):
    ''' Prints simple graphic showing sector-by-sector decay over images
        Intact: * and Changed: .
        Non-sequential sectors indicated by ---
    '''
    print('\n')
    last_offset = 0
    for item in changes:
        if item[1] == 0:
            symbols = '*' * NUM_IMAGES
        else:
            symbols = '*' * item[1] + '.' * (NUM_IMAGES - item[1])
        if ((item[0] - last_offset) != SECTOR_SIZE) and (last_offset != 0):
            print('---')
        print(str(item[0])+':'+symbols)
        last_offset = item[0]
    print('\n')

def process_file(filename, file_data, fo_graph, fo_csv):
    ''' Process and output one file from pre-loaded data. '''
    resident     = file_data['resident']
    frags        = file_data['frags']
    sectors      = file_data['sectors']
    total_sectors = len(sectors)
    print('\nFilename: '+filename)
    print('Total Sectors: '+str(total_sectors))
    changes = compute_changes_from_data(sectors)
    if OUTPUT_CHANGES_BY_IMAGE:
        show_changes_by_image(filename, total_sectors, changes)
    sectors_remaining = plot_persistence(filename, resident, frags, total_sectors, changes, fo_graph, fo_csv)
    if OUTPUT_FINAL_PERSISTENCE:
        final_persistence_percent = format(float(sectors_remaining / total_sectors * 100.0), '.2f')
        print('Final Persistence: '+str(final_persistence_percent)+
              '% ('+str(sectors_remaining)+'/'+str(total_sectors)+')\n')

if __name__ == "__main__":
    start_time = datetime.now()
    print("Start: " + str(start_time))
    conn = sqlite3.connect(DB)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA cache_size=-64000")
    conn.execute("PRAGMA synchronous=OFF")
    fo_graph = open('graphdata.out', 'w') if WRITE_FILE else None
    fo_csv   = open('processed.csv',  'w') if CREATE_PROCESSED_CSV else None
    if fo_csv:
        fo_csv.write('filename,ext,total_sectors,total_bytes,resident,frags,persistence...\n')

    parser = argparse.ArgumentParser(description='trace_file.py: process deleted file sector tracking DB')
    parser.add_argument('-a', action='store_true', help='process all files without prompting')
    parser.add_argument('filename', nargs='?', default=None, help='filename to process, or omit to list files')
    args = parser.parse_args()

    if args.a:
        filename = '*'
    elif args.filename is not None:
        filename = args.filename
    else:
        filename = input('Filename to process (null to list files in the DB, filename to process one file, * to process all): ')

    if filename == '':  # list files in the DB
        counter = 0
        c = conn.cursor()
        for row in c.execute('SELECT DISTINCT filename FROM '+DBT+';'):
            print(row[0])
            counter += 1
        print('\nTotal files: '+str(counter)+'\n')

    elif filename == '*':  # stream all files in one table scan — fast and memory-efficient
        total_files  = count_distinct_files(conn)
        print('Processing '+str(total_files)+' files...')
        file_counter = 0
        for fn, file_data in stream_all_files(conn):
            file_counter += 1
            print('('+str(file_counter)+'/'+str(total_files)+')', end=' ')
            process_file(fn, file_data, fo_graph, fo_csv)
        # Save the all-on-one plot once after all files are processed
        if CREATE_GRAPHS and PLOT_ALL_ON_ONE:
            plt.savefig('./plots/all.pdf', dpi=150)
            plt.clf()
            plt.close('all')

    elif '%' in filename:  # LIKE pattern — process all matching files
        total_files  = count_matching_files(conn, filename)
        print('Processing '+str(total_files)+' files matching: '+filename)
        file_counter = 0
        for fn, file_data in stream_matching_files(conn, filename):
            file_counter += 1
            print('('+str(file_counter)+'/'+str(total_files)+')', end=' ')
            process_file(fn, file_data, fo_graph, fo_csv)
        if CREATE_GRAPHS and PLOT_ALL_ON_ONE:
            plt.savefig('./plots/all.pdf', dpi=150)
            plt.clf()
            plt.close('all')

    else:  # process one specific file
        print('Loading data for: '+filename)
        file_data = load_file_data(filename, conn)
        if not file_data['sectors']:
            print('File not found in DB: '+filename)
        else:
            process_file(filename, file_data, fo_graph, fo_csv)
            if CREATE_GRAPHS and PLOT_ALL_ON_ONE:
                plt.savefig('./plots/all.pdf', dpi=150)
                plt.clf()
                plt.close('all')

    if fo_graph: fo_graph.close()
    if fo_csv:   fo_csv.close()
    conn.close()
    stop_time = datetime.now()
    print("Stop: " + str(stop_time))
    print("Elapsed: " + str(stop_time - start_time))

### End
