#!/usr/bin/env bash

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

