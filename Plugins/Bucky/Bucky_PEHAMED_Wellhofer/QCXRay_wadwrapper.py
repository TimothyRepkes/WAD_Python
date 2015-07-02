# PyWAD is open-source software and consists of a set of plugins written in python for the WAD-Software medical physics quality control software. 
# The WAD Software can be found on https://github.com/wadqc
# 
# The pywad package includes plugins for the automated analysis of QC images for various imaging modalities. 
# PyWAD has been originaly initiated by Dennis Dickerscheid (AZN), Arnold Schilham (UMCU), Rob van Rooij (UMCU) and Tim de Wit (AMC) 
#
#
# Changelog:
#
#
# Description of this plugin:
# 
#


__version__='01062015'
__author__ = 'aschilha'
import sys
import os
if not 'MPLCONFIGDIR' in os.environ:
    os.environ['MPLCONFIGDIR'] = "/tmp/.matplotlib" # if this folder already exists it must be accessible by the owner of WAD_Processor 
import matplotlib
matplotlib.use('Agg') # Force matplotlib to not use any Xwindows backend.

import dicom
import QCXRay_lib
try:
    import wadwrapper_lib
except ImportError:
    from pyWADLib import wadwrapper_lib

# MODULE EXPECTS PYQTGRAPH DATA: X AND Y ARE TRANSPOSED!

def logTag():
    return "[QCXRay_wadwrapper] "

##### Series wrappers
def xrayqc_series(data, results,**kwargs):
    """
    QCXRay_UMCU checks:
        Horizontal uniformity
        XRayEdges
        LowContrast
        DynamicRange
        MTF

    Workflow:
        2. Check data format
        3. Build and populate qcstructure
        4. Run tests
        5. Build xml output
        6. Build artefact picture thumbnail
    """
    inputfile = data.series_filelist[0]  # give me a filename

    ## 2. Check data format
    dcmInfile,pixeldataIn,dicomMode = wadwrapper_lib.prepareInput(inputfile,headers_only=False,logTag=logTag())

    ## 3. Build and populate qcstructure
    remark = ""
    qclib = QCXRay_lib.XRayQC()
    cs = QCXRay_lib.XRayStruct(dcmInfile,pixeldataIn)
    cs.verbose = False # do not produce detailed logging

    ## 4. Run tests
    error,msg = qclib.QC(cs)

    ## 5. Build xml output
    ## Struct now contains all the results and we can write these to the WAD IQ database
    stand = qclib.TableOrWall(cs)
    idname = '_'+stand

    labvals = qclib.ReportEntries(cs)
    tmpdict={}
    for key,val in labvals:
        results.addFloat(key+str(idname), val, quantity=str(key))

    ## 6. Build artefact picture thumbnail
    filename = 'test'+idname+'.jpg' # Use jpg if a thumbnail is desired

    qclib.saveAnnotatedImage(cs,filename)
    results.addObject('AnnotatedImage'+idname,filename)

def xrayheader_series(data,results,**kwargs):
    """
    Read selected dicomfields and write to IQC database

    Workflow:
        1. Read only headers
        2. Run tests
        3. Build xml output
    """
    info = 'qcwad'

    ## 1. read only headers
    dcmInfile = dicom.read_file(data.series_filelist[0][0], stop_before_pixels=True)

    ## 2. Run tests
    qclib = QCXRay_lib.XRayQC()

    ## Table or Wall? from distances and sensitivity; for well defined protocols to be defined in DESCRIPTION field
    cs = QCXRay_lib.XRayStruct(dcmInfile,None)
    cs.verbose = False # do not produce detailed logging
    dicominfo = qclib.DICOMInfo(cs,info)
    idname = '_'+qclib.TableOrWall(cs)

    ## 3. Build xml output
    floatlist = [
        'Exposure (mAs)',
        'DistanceSourceToDetector (mm)',
        'ExposureTime (ms)',
        'ImageAreaDoseProduct',
        'Sensitivity',
        'kVp'
    ]

    results.addChar('pluginversion'+idname, str(qclib.qcversion)) # do not specify level, use default from config
    for di in dicominfo:
        if di[0] in floatlist:
            results.addFloat(di[0]+idname, di[1]) # do not specify level, use default from config
        else:
            results.addChar(di[0]+idname, str(di[1])[:min(len(str(di[1])),128)]) # do not specify level, use default from config

    results.addChar('room'+idname, cs.guessroom.name) # do not specify level, use default from config
    results.addChar('stand'+idname, qclib.TableOrWall(cs)) # do not specify level, use default from config
