# dicomkit

Python Q&R from a remote or local Horos server.

Specific support for CMRR MB-EPI DICOM Physiolog files which
use a private SOP class UID and cause display problems with Horos
and C-STORE problems with dcmtk.

### Dependencies
Implemented using pynetdicom 2.0 which supports private SOP classes.
