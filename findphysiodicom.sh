#!/usr/bin/env bash
#
# Simple query of DICOM Physiolog files from a Horos database
#
# Tested with:
# - macOS 10.13.6 High Sierra
# - dcmtk: findscu v3.6.5 2019-10-28
# - GNU bash, version 3.2.57(1)-release (x86_64-apple-darwin17)
#
# Add the following node to Horos (Preferences > Locations):
# 127.0.0.1 | localsu | 11113 | Q&R Checked | C-MOVE | Send Checked | TLS No | Local QR script | ELE
#
# AUTHOR : Mike Tyszka
# PLACE  : Caltech
# DATES  : 2021-07-08 JMT Adapt from old CBICQC code

if [ $# -lt 1 ]
then
    echo "USAGE : findphysiodicom.sh <Patient ID>"
    echo "EXAMPLE : findphysiodicom.sh CC1234"
    exit
fi

pid=$1

# Debugging and verbose output
verbose="-d -v"

# Remote DICOM server info
# Edit for local Horos setup
remote_aet=evendim
remote_hostname=127.0.0.1
remote_port=11112

# Local DICOM server info
# This can be constant across systems
local_aet=localscu
local_port=11113

# Construct search keys for patient and series
search_keys=" -k 0008,0052=""SERIES"" -k 0010,0020=""*${pid}*"" -k 0008,103e=""*Physiolog*"" "

# Query context - study level
context="-S"

findscu ${verbose} ${context} ${search_keys} ${remote_hostname} ${remote_port}
