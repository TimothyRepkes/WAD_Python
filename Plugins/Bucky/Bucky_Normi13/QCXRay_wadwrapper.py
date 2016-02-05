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


__version__='20160205'
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

# helper functions
"""
    roomWKZ1 = QCXRay_lib.Room('WKZ1', tablepid=70,wallpid=50,
                               linepairmarkers={'type':'RXT02',mm0.6':[-83.,-25.],'mm1.0':[-99.,-8.]},artefactborderpx=[5,5,5,5],
                               detectorname={'SN152495':'Tafel', 'SN152508':'Wand', 'SN1522YG':'Klein1', 'SN151685':'Groot2'})
    <params>
      <roomname>WKZ1</roomname>
      <tablepidmm>70</tablepidmm>
      <wallpidmm>50</wallpidmm>
      <linepair_type>RXT02</linepair_type>
      <linepairs>
        <mm1.0 x="-99.0" y="-8.0" />
        <mm0.6 x="-83.0" y="-25.0" />
      </linepairs>
      <artefactborderpx>
        <xmin px="5" />
        <xmax px="5" />
        <ymin px="5" />
        <ymax px="5" />
      </artefactborderpx>
      <detector_name>
        <names SN151685="Groot2" SN1522YG="Klein1" SN152495="Tafel" SN152508="Wand" />
      </detector_name>
    </params>
"""
def _getRoomDefinition(params):
    # Use the params in the config file to construct an Scanner object
    try:
        # a name for identification
        roomname = params.find('roomname').text

        # Need to know the type of linepairs insert
        linepair_type = params.find('linepair_type').text
        if not linepair_type in ['None','RXT02','38']:
            raise ValueError('Incorrect linepair type %s'%linepair_type)
        
        # load the locations of markers on the linepair pattern. if these are not given, use the hardcoded values
        linepairmarkers = {}
        try:
            markers = params.find('linepairs')
            if linepair_type == 'RXT02':
                mnames = ['mm1.0','mm0.6']
            elif linepair_type == '38':
                mnames = ['mm1.8','mm0.6','mm1.4','mm4.6']
                
            for mname in mnames:
                marker  = markers.find(mname)
                linepairmarkers[mname] = [ float(marker.attrib['x']), float(marker.attrib['y']) ]
        except:
            print logTag()+' exact locations of markers on linepair pattern not supplied by config. Using empirical values; please check if these are valid here.'
        linepairmarkers['type'] = linepair_type
        
        # border to exclude
        artefactborderpx = [0,0,0,0]
        try:
            bpxs = params.find('artefactborderpx')
            mnames = ['xmin','xmax','ymin','ymax']
            for i,mname in enumerate(mnames):
                marker  = bpxs.find(mname)
                artefactborderpx[i] = int(marker.attrib['px'])
        except:
            print logTag()+' no border supplied by config. Using [0,0,0,0].'
            
        # load detector names
        detectorname = {}
        try:
            dets_names = params.find('detector_name')
            names = dets_names.find('names')
            for a,b in names.items():
                detectorname[a] = b
        except:
            print logTag()+' no explicit detector_name pairs defined in config.'

        # Source to Detector distance and Patient to Detector distance for wall and table (both in mm)
        tablepidmm  = float(params.find('tablepidmm').text)
        wallpidmm   = float(params.find('wallpidmm').text)

        outvalue    = -1 # not supplied
        wallsidmm   = -1 # not supplied
        tablesidmm  = -1 # not supplied
        
        # no artificial thresholds present or needed
        return QCXRay_lib.Room(roomname, outvalue=outvalue,
                               tablesid=tablesidmm, wallsid=wallsidmm, 
                               tablepid=tablepidmm, wallpid=wallpidmm,
                               artefactborderpx=artefactborderpx,
                               linepairmarkers=linepairmarkers,detectorname=detectorname)
    except AttributeError,e:
        raise ValueError(logTag()+" missing room definition parameter!"+str(e))


###### Series wrappers
def xrayqc_series(data, results, params):
    """
    QCXRay_UMCU checks:
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
    room = _getRoomDefinition(params)
    cs = QCXRay_lib.XRayStruct(dcmInfile,pixeldataIn,room)
    cs.verbose = False # do not produce detailed logging

    ## 4. Run tests
    error,msg = qclib.QC(cs)

    ## 5. Build xml output
    ## Struct now contains all the results and we can write these to the WAD IQ database
    stand,detector = qclib.TableOrWall(cs)
    idname = '_'+stand+'_'+detector

    ## first Build artefact picture thumbnail
    label = 'normi13'
    filename = '%s%s.jpg'%(label,idname) # Use jpg if a thumbnail is desired

    qclib.saveAnnotatedImage(cs,filename)
    results.addObject('%s%s'%(label,idname),filename)

    labvals = qclib.ReportEntries(cs)
    tmpdict={}
    for elem in labvals:
        #labvals.append( {'name':'label','value':0, 'quantity':'columnname','level':'1:default, 2: detail','pos':missing or a number} )
        # if no pos given, the next one will be given
        # if no quantity given, 'name' will be used
        # if no level given, the default will be used
        quan = elem['quantity'] if 'quantity' in elem else str(elem['name'])
        level = elem['level'] if 'level' in elem else None
        rank = elem['rank'] if 'rank' in elem else None
        results.addFloat(elem['name']+str(idname), elem['value'], quantity=quan, level=level,rank=rank)


def xrayqc_uniformity_series(data, results, params):
    """
    QCXRay_uniformity checks:
        Uniformity
        Artefacts
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
    room = _getRoomDefinition(params)
    cs = QCXRay_lib.XRayStruct(dcmInfile,pixeldataIn,room)
    cs.verbose = False # do not produce detailed logging

    ## 4. Run tests
    error,msg = qclib.QCUnif(cs)

    ## 5. Build xml output
    ## Struct now contains all the results and we can write these to the WAD IQ database
    stand,detector = qclib.TableOrWall(cs)
    idname = '_'+stand+'_'+detector

    ## First Build artefact picture thumbnail
    label = 'unif'
    filename = '%s%s.jpg'%(label,idname) # Use jpg if a thumbnail is desired

    qclib.saveAnnotatedImage(cs,filename)
    results.addObject('%s%s'%(label,idname),filename)

    labvals = qclib.ReportEntries(cs)
    tmpdict={}
    for elem in labvals:
        #labvals.append( {'name':'label','value':0, 'quantity':'columnname','level':'1:default, 2: detail','pos':missing or a number} )
        # if no pos given, the next one will be given
        # if no quantity given, 'name' will be used
        # if no level given, the default will be used
        quan = elem['quantity'] if 'quantity' in elem else str(elem['name'])
        level = elem['level'] if 'level' in elem else None
        rank = elem['rank'] if 'rank' in elem else None
        results.addFloat(elem['name']+str(idname), elem['value'], quantity=quan, level=level,rank=rank)


def xrayheader_series(data,results,params):
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
    room = _getRoomDefinition(params)

    ## Table or Wall? from distances and sensitivity; for well defined protocols to be defined in DESCRIPTION field
    cs = QCXRay_lib.XRayStruct(dcmInfile,None,room)
    cs.verbose = False # do not produce detailed logging
    dicominfo = qclib.DICOMInfo(cs,info)
    stand,detector = qclib.TableOrWall(cs)
    idname = '_'+stand+'_'+detector

    ## 3. Build xml output
    floatlist = [
        'Exposure (mAs)',
        'DistanceSourceToDetector (mm)',
        'ExposureTime (ms)',
        'ImageAreaDoseProduct',
        'Sensitivity',
        'kVp'
    ]
    offset = -26
    results.addChar('pluginversion'+idname, str(qclib.qcversion)) # do not specify level, use default from config
    for elem in dicominfo:
        quan = elem['quantity'] if 'quantity' in elem else str(elem['name'])
        level = elem['level'] if 'level' in elem else None # if not specify level, use default from config
        rank = elem['rank'] if 'rank' in elem else None
        if elem['name'] in floatlist:
            results.addFloat(elem['name']+str(idname), elem['value'], quantity=quan, level=level,rank=rank)
        else:
            results.addChar(elem['name']+str(idname), str(elem['value'])[:min(len(str(elem['value'])),128)], quantity=quan, level=level,rank=rank)

    results.addChar('room'+idname, cs.forceRoom.name) # do not specify level, use default from config
    results.addChar('stand'+idname, stand, level=1,rank=offset+1) # do not specify level, use default from config
    results.addChar('detector'+idname, detector, level=1,rank=offset+2) # do not specify level, use default from config
