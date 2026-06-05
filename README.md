# DECay ANalysis Tool (DECANT)



Last Updated: 6-5-2026

Original version: 5-29-2026



##### Overview



Code generates sector-level file decay data and visualizations from a set of sequential disk (media) images. Tested on FAT and NTFS filesystems; others may work but have not been tested.

###### 

###### config.ini



Contains runtime parameters for adiff.py and trace\_file.py.



###### adiff.py



Deleted files are detected between images 0 and 1; the contents of the sectors of these files are tracked through the image set via md5 hashes. idifference2.py (part of fiwalk) is used to detect deleted files and writes results to a temporary dfxml file. Deleted sector information is written to a local sqlite3 database.



###### trace\_file.py



Prompts the user to select a single deleted file to process or process all files in the database. Reads from the database to compute decay data and optionally (see config.ini) outputs data files and vizualizations.



###### cleanup.sh



Simple script to remove temporary and output files from a directory, e.g., recommended when re-running an analysis.



##### Installation



Tested on Ubuntu 24.04.3 LTS in a WSL2 environment on Windows 11. Should work on any recent Ubuntu install.



###### Update and install latest Python:

\&nbsp;\&nbsp;$ sudo apt update

\&nbsp;\&nbsp;$ sudo apt install software-properties-common

\&nbsp;\&nbsp;$ sudo add-apt-repository ppa:deadsnakes/ppa

\&nbsp;\&nbsp;$ sudo apt update

\&nbsp;\&nbsp;$ sudo apt install python3.13

\&nbsp;\&nbsp;$ sudo apt install python3.13-venv python3.13-dev



###### Create and activate virtual environment:

\&nbsp;\&nbsp;$ python3.13 -m venv decant

\&nbsp;\&nbsp;$ source decant/bin/activate

\&nbsp;\&nbsp;(decant) $ pip install --upgrade pip

\&nbsp;\&nbsp;(decant) $ mkdir code; cd code



###### Download code:

\&nbsp;\&nbsp;https://github.com/jjonesu/DeletedFilePersistence

\&nbsp;\&nbsp;put adiff.py, cleanup.sh, config.ini, trace\_file.py, in \~/code directory



###### Install necessary packages:

\&nbsp;\&nbsp;(decant) $ sudo apt install sleuthkit

\&nbsp;\&nbsp;(decant) $ pip install git+https://github.com/dfxml-working-group/dfxml\_python.git

\&nbsp;\&nbsp;(decant) $ pip install numpy

\&nbsp;\&nbsp;(decant) $ pip install matplotlib



##### Usage



Place the disk (media) images in an accessible directory.

\&nbsp;\&nbsp;This directory may be the same as the dedicated directory in the next step but does not need to be.

\&nbsp;\&nbsp;If not, be sure to use paths when listing the images in config.ini.

Copy cleanup.sh and the template config.ini file from \~/code to a dedicated directory for these images and edit config.ini accordingly.

Run adiff.py from this directory (the local config.ini file will be used):

\&nbsp;\&nbsp;(decant) $ python3 \~/code/adiff.py

\&nbsp;\&nbsp;Run should create temp.dfxml and deleted.db in the local directooy.

Run trace\_file.py from this directory (the local config.ini file will be used):

\&nbsp;\&nbsp;(decant) $ python3 \~/code/trace\_file.py

\&nbsp;\&nbsp;At the prompt, select one option:

\&nbsp;\&nbsp;\&nbsp;\&nbsp;list all files in the db

\&nbsp;\&nbsp;\&nbsp;\&nbsp;process all files in the db

\&nbsp;\&nbsp;\&nbsp;\&nbsp;process one file in the db

\&nbsp;\&nbsp;Run should (depending on options set in config.ini) create/output the following:

\&nbsp;\&nbsp;\&nbsp;\&nbsp;plot line graphs to PDF (in directory ./plots)

\&nbsp;\&nbsp;\&nbsp;\&nbsp;write raw graph data to graphdata.out

\&nbsp;\&nbsp;\&nbsp;\&nbsp;plot all file decay curves on one graph or separate graphs

\&nbsp;\&nbsp;\&nbsp;\&nbsp;show sector-by-sector decay at runtime

\&nbsp;\&nbsp;\&nbsp;\&nbsp;show final % persistence at runtime

\&nbsp;\&nbsp;\&nbsp;\&nbsp;write processed data to CSV

\&nbsp;\&nbsp;trace\_file.py has optional flags to bypass the prompt (e.g., to run adiff and trace\_file sequentially or scripted and unattended):

\&nbsp;\&nbsp;\&nbsp;\&nbsp;(decant) $python3 trace\_file.py -a\&nbsp;\&nbsp;\&nbsp;\&nbsp;\&nbsp;\&nbsp;\&nbsp;\&nbsp;\&nbsp;\&nbsp;\&nbsp;\&nbsp;\&nbsp;\&nbsp;\&nbsp;\&nbsp;\&nbsp;\&nbsp;# process all files, no prompt

\&nbsp;\&nbsp;\&nbsp;\&nbsp;(decant) $python3 trace\_file.py somefile.jpg\&nbsp;\&nbsp;\&nbsp;\&nbsp;\&nbsp;\&nbsp;\&nbsp;\&nbsp;# process one specific file, no prompt

\&nbsp;\&nbsp;\&nbsp;\&nbsp;(decant) $python3 trace\_file.py\&nbsp;\&nbsp;\&nbsp;\&nbsp;\&nbsp;\&nbsp;\&nbsp;\&nbsp;\&nbsp;\&nbsp;\&nbsp;\&nbsp;\&nbsp;\&nbsp;\&nbsp;\&nbsp;\&nbsp;\&nbsp;\&nbsp;\&nbsp; # interactive prompt as before

\&nbsp;\&nbsp;\&nbsp;\&nbsp;(decant) $python3 trace\_file.py --help\&nbsp;\&nbsp;\&nbsp;\&nbsp;\&nbsp;\&nbsp;\&nbsp;\&nbsp;\&nbsp;\&nbsp;\&nbsp;\&nbsp;\&nbsp;\&nbsp;# shows usage

\&nbsp;\&nbsp;The specific file mode supports wildcards (SQL syntax), e.g.,

\&nbsp;\&nbsp;\&nbsp;\&nbsp;%.jpg\&nbsp;\&nbsp;\&nbsp;\&nbsp;\&nbsp;\&nbsp;\&nbsp;\&nbsp;\&nbsp;\&nbsp;\&nbsp;\&nbsp;\&nbsp;\&nbsp;\&nbsp;\&nbsp; # all .jpg files

\&nbsp;\&nbsp;\&nbsp;\&nbsp;%.mp4\&nbsp;\&nbsp;\&nbsp;\&nbsp;\&nbsp;\&nbsp;\&nbsp;\&nbsp;\&nbsp;\&nbsp;\&nbsp;\&nbsp;\&nbsp;\&nbsp;\&nbsp;\&nbsp; # all .mp4 files

\&nbsp;\&nbsp;\&nbsp;\&nbsp;%Camera00%\&nbsp;\&nbsp;\&nbsp;\&nbsp;\&nbsp;\&nbsp;\&nbsp;\&nbsp;\&nbsp;\&nbsp;\&nbsp;\&nbsp;# all files with Camera00 in the path

\&nbsp;\&nbsp;\&nbsp;\&nbsp;%20251113%\&nbsp;\&nbsp;\&nbsp;\&nbsp;\&nbsp;\&nbsp;\&nbsp;\&nbsp;\&nbsp;\&nbsp;\&nbsp;\&nbsp;# all files from that date

\&nbsp;\&nbsp;\&nbsp;\&nbsp;Camera00/event/%.jpg\&nbsp;\&nbsp;# .jpg files under a specific directory

Examples:

\&nbsp;\&nbsp;Run both components in one step (assuming a local config.ini file has been prepared) and process all files:

\&nbsp;\&nbsp;\&nbsp;\&nbsp;(decant) $ python3 \~/code/adiff.py; python3 \~/code/trace\_file.py -a

\&nbsp;\&nbsp;Run both components in one step (assuming a local config.ini file has been prepared) but just process JPG files:

\&nbsp;\&nbsp;\&nbsp;\&nbsp;(decant) $ python3 \~/code/adiff.py; python3 \~/code/trace\_file.py %.jpg

\&nbsp;\&nbsp;Sample data is described and linked in the AudioData folder.



##### Notes



If want to re-run, recommend running cleanup.sh first; code should check and reset anyway, but best to run cleanup.sh.

If have temp.dfxml from a prior run and just want to reload the db, set HAVE\_TEMP\_DFXML in config.ini to True.

Any ERROR messages generated by idifference2.py will display on the console, but idifference2.py INFO and WARNING messages are suppressed by trace\_file.py.

Once adiff.py has run, no need to rerun if want to trace different files; just run trace\_file.py.

\&nbsp;\&nbsp;adiff.py processes the raw data and saves it in the db

\&nbsp;\&nbsp;trace\_file.py visualizes and creates other useful data formats from the db

To leave the virtual environment:

\&nbsp;\&nbsp;(decant) $ deactivate

\&nbsp;\&nbsp;$



##### End

