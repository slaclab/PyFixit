from os import path,getenv
from pydm import Display
import meme.names
from epics import caget, caput, caget_many
import datetime, pytz, requests, json
import numpy as np
from PyQt5.QtWidgets import QFileDialog

class MyDisplay(Display):
  def __init__(self, parent=None, args=None, macros=None):
    super(MyDisplay, self).__init__(parent=parent,args=args, macros=macros)
    self.getCurrPushButton.clicked.connect(self.getCurr)
    self.getHistPushButton.clicked.connect(self.getHist)
    self.setCurrPushButton.clicked.connect(self.setCurr)
    self.setHistPushButton.clicked.connect(self.setHist)
    self.loadListPushButton.clicked.connect(self.loadList)
    self.saveListPushButton.clicked.connect(self.saveList)
    self.globalMessage.setText("Ready")
    self.histMessage.clear()
    self.currMessage.clear()
    self.setCurrPushButton.setEnabled(False)
    self.setHistPushButton.setEnabled(False)
    self.lclsUrl = "http://lcls-archapp.slac.stanford.edu/retrieval/data/getDataAtTime?at="
    self.facetUrl = "http://facet-archapp.slac.stanford.edu/retrieval/data/getDataAtTime?at="
    self.timezone = pytz.timezone('US/Pacific')
    self.cagetTimeOut=0.1

  def ui_filename(self):
    return('fixit.ui')

  def ui_filepath(self):
    return path.join(path.dirname(path.realpath(__file__)), self.ui_filename())
    
  def makepvList(self):
    self.pvs = self.inputPVs.toPlainText().split()
    self.pvList=[]
    for pv in self.pvs:
      if '%' in pv:
        minilist=meme.names.list_pvs(pv)
        for eachpv in minilist:
          self.pvList.append(eachpv)
      else:
        self.pvList.append(pv)

  def getCurr(self):
    self.globalMessage.setText("Getting current values...")
    self.makepvList()
    self.currVals=[]
    outtext=[]
    try:
      self.currVals=caget_many(self.pvList)
    except:
      print("At least one PV doesn't connect. Trying individually...")
      for pv in self.pvList:
        try:
          if not meme.names.list_pvs(pv)==[]:
            self.currVals.append(caget(pv))
          else:
            self.currVals.append(np.nan)
        except:
          self.currVals.append(np.nan)
    while None in self.currVals:
      self.currVals[self.currVals.index(None)]=np.nan
    for pp,pv in enumerate(self.pvList):
      try:
        outtext.append(f"{pv} is {self.currVals[pp]:g}")
      except:
        print(f"Problems with {pv} {self.currVals[pp]}")
    self.currValsTextBrowser.clear()
    self.currValsTextBrowser.append('\n'.join(outtext))
    
    currTime=datetime.datetime.now()
    self.currMessage.setText(f"from {currTime.strftime('%m/%d/%y %H:%M:%S')}")
    self.setCurrPushButton.setEnabled(True)
    self.globalMessage.setText("Fetched current values.")

  def setCurr(self):
    self.globalMessage.setText("Setting PVs to 'Current' values")
    for nn,pv in enumerate(self.pvList):
      if not np.isnan(self.currVals[nn]):
        caput(pv,self.currVals[nn])
        print(f"Set {pv} to {self.currVals[nn]}")
      else:
        print(f"Skipped {pv} because caget failed.")
    self.globalMessage.setText("Set PVs to 'Current' values")

    
  def valiDate(self,indate,intime):
    try:
      point=datetime.datetime.strptime(indate+' '+intime,'%m/%d/%Y %H:%M')
    except:
      try:
        point=datetime.datetime.strptime(indate+' '+intime,'%m/%d/%y %H:%M')
      except:
        if '-' in indate:
          indate=indate.replace('-','/')
          parts=indate.split('/')
          print(len(parts))
          if len(parts)>1 and len(parts[2])==2:
            parts[2]=str(int(parts[2])+2000)
          indate=parts[0]+'/'+parts[1]+'/'+parts[2]
        try:
          point=datetime.datetime.strptime(indate+' '+intime,'%m/%d/%Y %H:%M')
        except:
          point=f'Problems parsing {indate} {intime} as mm/dd/yyy hh:mm'
    return point

  def getHist(self):
    self.globalMessage.setText("Getting archived values...")
    mdf=getenv('MATLABDATAFILES')
    if 'lcls' in mdf:
      self.url=self.lclsUrl
    else:
      self.url=self.facetUrl
    self.makepvList()
    self.pastDate=self.dateLineEdit.text()
    self.pastTime=self.timeLineEdit.text()
    histTime=self.valiDate(self.pastDate,self.pastTime)
    if type(histTime)==str:
      self.histMessage.setText(histTime)
      return

# Assemble formatted timestring
    dst_check = self.timezone.localize(histTime)
    if bool(dst_check.dst()):
      timezone = '-07:00'
    else:
      timezone = '-08:00'
    base_url = self.url+histTime.strftime("%Y-%m-%dT%H:%M:%S.%f")+timezone
    self.histVals=[]
    outtext=[]
    resp=requests.post(base_url,json=self.pvList)
    resp.raise_for_status()
    for pv in self.pvList:
      try:
        val = round(resp.json()[pv]['val'], 4)
        self.histVals.append(val)
      except:
        self.histVals.append(np.nan)
      outtext.append(f"{pv} was {self.histVals[-1]}")
    self.histValsTextBrowser.clear()
    self.histValsTextBrowser.append('\n'.join(outtext))
    self.histMessage.setText(f"from {histTime.strftime('%m/%d/%y %H:%M:%S')}")
    self.setHistPushButton.setEnabled(True)
    self.globalMessage.setText("Fetched archived values.")
    
  def setHist(self):
    self.globalMessage.setText("Setting PVs to archived values")
    for nn,pv in enumerate(self.pvList):
      if not np.isnan(self.histVals[nn]):
        caput(pv,self.histVals[nn])
        print(f"Set {pv} to {self.histVals[nn]}")
      else:
        print(f"Skipped {pv} because the archive fetch failed.")
    self.globalMessage.setText("Set PVs to archived values")

  def loadList(self):
    mdf=getenv('MATLABDATAFILES')
    if 'lcls' in mdf:
      pathName='/u1/lcls/matlab/config/fixit_configs/json'
    else:
      pathName='/u1/facet/matlab/config/fixit_configs/json'
    fileDial=QFileDialog()
    fname_tuple=fileDial.getOpenFileName(None,'Load config file',pathName,'*.json')
    with open(fname_tuple[0],'r') as ff:
      self.pvList=json.load(ff)
    self.inputPVs.setPlainText('\n'.join(self.pvList))
    justFile=fname_tuple[0].split('/')
    self.globalMessage.setText(f"Loaded file {justFile[-1]}")
    self.currValsTextBrowser.clear()
    self.currVals=[]
    self.histValsTextBrowser.clear()
    self.histVals=[]
    
  def saveList(self):
    self.makepvList()
    print(self.pvList)
    mdf=getenv('MATLABDATAFILES')
    if 'lcls' in mdf:
      pathName='/u1/lcls/matlab/config/fixit_configs/json'
    else:
      pathName='/u1/facet/matlab/config/fixit_configs/json'
    fileDial=QFileDialog()
    fname_tuple=fileDial.getSaveFileName(None,'Save config file',pathName,'*.json')
#    print(fname_tuple)
    if fname_tuple[0].endswith('.json'):
      fname=fname_tuple[0]
    else:
      fname=fname_tuple[0]+'.json'
#    print(fname)
    with open(fname,'w+') as ff:
      json.dump(self.pvList,ff)
    justFile=fname.split('/')
    self.globalMessage.setText(f"Saved file {justFile[-1]}")    
    
        