# DeletedFilePersistence
Two Python 3.x programs to facilitate the study of deleted file persistence (decay). This is prototype code and configuration is done via settings in the code (noted near the top of each program).

Requires: idifference2.py (which requires fiwalk and dfxml)

adiff.py: (Run this first) Takes a series of raw hard disk images from a single system, finds deleted files between images 0 and 1, then tracks contents of those deleted files in images 1...N. Data is stored in a local sqlite3 database.
  Configuration parameters (see "User.set vars" in the source):
    ### User-set vars
    IDIFF2_PATH='/path_to/dfxml/python/idifference2.py' # full path to idifference2.py
    SECTOR_SIZE=512 # 512,4096,... use imaged drive sector size
    IMAGE_LIST=['image0.img','image1.img',...] # a Python list of image names; they will be processed in this order (this matters...)
    HAVE_TEMP_DFXML=True # True if you already have a temp.dfxml file (idiff output for images 0-1), otherwise False; saves time

trace_file.py: (Run this second) Processes a sqlite3 database of tracked deleted files (like that produced by adiff.py).
  Command line: after running, user is prompted to just list the files in the DB, process all files in the DB, or process a single file
  Configuration parameters (see "Globals" and Flags" in the source):
    # Globals
    DB = 'deleted.db' # DB to use
    DBT = 'deleted_files' # DB table to use
    NUM_IMAGES = 13 # number of images originally processed
    SECTOR_SIZE = 512 # sector size of imaged media filesystem
    # Flags (these variables control the output; any combination is valid; set to False to disable that output)
    CREATE_GRAPHS = True # plots line graphs of persistence as PDF files; written to ./plots/filename.pdf
    WRITE_FILE = True # writes graph data to a file (graphdata.out)
    PLOT_ALL_ON_ONE = True # plots all lines on one graph; dense but interesting; otherwise one plot per file
    OUTPUT_CHANGES_BY_IMAGE = True # outputs persistence (* and .) for each sector across the images
    OUTPUT_FINAL_PERSISTENCE = True # output final % persistence
    CREATE_PROCESSED_CSV = True # write processed file data to a sqlite3 db file for subsequent analysis

Working files (temp.dfxml, deleted.db) and output files will be written to the current working directory.
