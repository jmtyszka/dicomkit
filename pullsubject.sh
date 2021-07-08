#!/usr/bin/env bash
#
# Simple query and retrive of a Horos SCP from the command line
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
# DATES  : 2021-07-08 JMT Update from old CBICQC code

if [ $# -lt 1 ]
then
    echo "USAGE : pulldicom.sh <Patient ID>"
    echo "EXAMPLE : pulldicom.sh CC1234"
    exit
fi

pid=$1

debug=""

# Remote DICOM server info
remote_aet=evendim
remote_hostname=127.0.0.1
remote_port=11112

# Local DICOM server info
local_aet=localscu
local_port=11113

# Construct search keys
#search_keys="-k 0010,0020=""*${pid}*"" -k 0008,103e=""*Physio*"""
#search_keys="-k 0008,103e=""*Physio*"""
search_keys="-k 0010,0020=""*${pid}*"""

# Output directory
dicom_dir="dicom/${pid}/1"
mkdir -p ${dicom_dir}

context="-S -k 0008,0052="STUDY""

# findscu -d ${context} -k 0008,103e="*Physio*" -k 0010,0010="Jod-2c2*" localhost 11112

cmd="movescu -aet ${local_aet} --port ${local_port} ${debug} ${context} ""${search_keys}"" -od ${dicom_dir} ${remote_hostname} ${remote_port}"
echo $cmd
$cmd

