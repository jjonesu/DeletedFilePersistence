# DECay ANalysis Tool (DECANT)



Last Updated: 6-5-2026

Original version: 9-16-2016



##### Citation



If you use this code in published work, please cite:



Jones, James H., and Tahir M. Khan. "A method and implementation for the empirical study of deleted file persistence in digital devices and media." 2017 IEEE 7th Annual Computing and Communication Workshop and Conference (CCWC). IEEE, 2017.



##### Overview



Code generates sector-level file decay data and visualizations from a set of sequential disk (media) images. Tested on FAT and NTFS filesystems; others may work but have not been tested.

###### 

###### config.ini



* Contains runtime parameters for adiff.py and trace\_file.py.



###### adiff.py



* Deleted files are detected between images 0 and 1; the contents of the sectors of these files are tracked through the image set via md5 hashes. idifference2.py (part of fiwalk) is used to detect deleted files and writes results to a temporary dfxml file. Deleted sector information is written to a local sqlite3 database.



###### trace\_file.py



* Prompts the user to select a single deleted file to process or process all files in the database. Reads from the database to compute decay data and optionally (see config.ini) outputs data files and vizualizations.



###### cleanup.sh



* Simple script to remove temporary and output files from a directory, e.g., recommended when re-running an analysis.



##### Installation



Tested on Ubuntu 24.04.3 LTS in a WSL2 environment on Windows 11. Should work on any recent Ubuntu install.



###### Update and install latest Python:

* $ sudo apt update
* $ sudo apt install software-properties-common
* $ sudo add-apt-repository ppa:deadsnakes/ppa
* $ sudo apt update
* $ sudo apt install python3.13
* $ sudo apt install python3.13-venv python3.13-dev



###### Create and activate virtual environment:

* $ python3.13 -m venv decant
* $ source decant/bin/activate
* (decant) $ pip install --upgrade pip
* (decant) $ mkdir code; cd code



###### Download code:

* https://github.com/jjonesu/DeletedFilePersistence
* put adiff.py, cleanup.sh, config.ini, trace\_file.py, in \~/code directory



###### Install necessary packages:

* (decant) $ sudo apt install sleuthkit
* (decant) $ sudo apt install git
* (decant) $ pip install git+https://github.com/dfxml-working-group/dfxml\_python.git
* (decant) $ pip install numpy
* (decant) $ pip install matplotlib



##### Usage



Place the disk (media) images in an accessible directory.

* This directory may be the same as the dedicated directory in the next step but does not need to be.
* If not, be sure to use paths when listing the images in config.ini.

Copy cleanup.sh and the template config.ini file from \~/code to a dedicated directory for these images and edit config.ini accordingly.

Run adiff.py from this directory (the local config.ini file will be used):

* (decant) $ python3 \~/code/adiff.py
* Run should create temp.dfxml and deleted.db in the local directory.

Run trace\_file.py from this directory (the local config.ini file will be used):

* (decant) $ python3 \~/code/trace\_file.py
* At the prompt, select one option:

  * list all files in the db
  * process all files in the db
  * process one file in the db
* Run should (depending on options set in config.ini) create/output the following:

  * plot line graphs to PDF (in directory ./plots)
  * write raw graph data to graphdata.out
  * plot all file decay curves on one graph or separate graphs
  * show sector-by-sector decay at runtime
  * show final % persistence at runtime
  * write processed data to CSV
* trace\_file.py has optional flags to bypass the prompt (e.g., to run adiff and trace\_file sequentially or scripted and unattended):

  * (decant) $python3 trace\_file.py -a                  # process all files, no prompt
  * (decant) $python3 trace\_file.py somefile.jpg        # process one specific file, no prompt
  * (decant) $python3 trace\_file.py                     # interactive prompt as before
  * (decant) $python3 trace\_file.py --help              # shows usage
* The specific file mode supports wildcards (SQL syntax), e.g.,

  * %.jpg                 # all .jpg files
  * %.mp4                 # all .mp4 files
  * %Camera00%            # all files with Camera00 in the path
  * %20251113%            # all files from that date
  * Camera00/event/%.jpg  # .jpg files under a specific directory

Examples:

* Run both components in one step (assuming a local config.ini file has been prepared) and process all files:

  * (decant) $ python3 \~/code/adiff.py; python3 \~/code/trace\_file.py -a
* Run both components in one step (assuming a local config.ini file has been prepared) but just process JPG files:

  * (decant) $ python3 \~/code/adiff.py; python3 \~/code/trace\_file.py %.jpg
* Sample data is described and linked in the AudioData folder.



##### Notes



If want to re-run, recommend running cleanup.sh first; code should check and reset anyway, but best to run cleanup.sh.

If have temp.dfxml from a prior run and just want to reload the db, set HAVE\_TEMP\_DFXML in config.ini to True.

Any ERROR messages generated by idifference2.py will display on the console, but idifference2.py INFO and WARNING messages are suppressed by trace\_file.py.

Once adiff.py has run, no need to rerun if want to trace different files; just run trace\_file.py.

* adiff.py processes the raw data and saves it in the db
* trace\_file.py visualizes and creates other useful data formats from the db

To leave the virtual environment:

* (decant) $ deactivate
* $



##### End

