import configparser
import csv
import decimal
from decimal import Decimal
import os
import subprocess
import time
from __modify_spro import *

def Get_ConfigValue(ConfigSection,ConfigKey):                                                       # Function to retrieve values from the INI file structure
    ConfigValue = CFconfig[ConfigSection][ConfigKey]
    return ConfigValue

CFconfig = configparser.ConfigParser()                                                              # Initialize Config
CFconfig.read('__Runconfig.cftconf')                                                                # Read Config
batchVar_Name = Get_ConfigValue('PreProcessing','batchVar')                                         # Get name of batch variable
batchVar_Values = Get_ConfigValue('PreProcessing','batchVarValues').split(" ")                      # Get values for batch variable, format the as a list by splitting
flowQuantities = ['userdef.' + item for item in Get_ConfigValue('PostProcessing','FlowQuantities').split(" ")]    # Get floq quantities for post-processing
decimal.getcontext().prec = 9                                                                       # Set user alterable precision to 9 places e.g. 0.142857143

def Print_Runtime(time_start):                                                                      # Function to measure the wall clock time for different operations (meshing, solver run)
    time_elapsed = time.time() - time_start
    print("RUNTIME\t[HH:MM:SS]\t",time.strftime("%H:%M:%S", time.gmtime(time_elapsed)),"\n")    
    return time_elapsed

def SMP_Solver(SMP_Args):                                                                           # Function that will call Simerics
    SMP_Cli=[os.path.sep.join(Get_ConfigValue('ProgramPath','Simerics').split("/"))]
    [SMP_Cli.append(item) for item in SMP_Args]                                                     # Create Simerics batch call e.g. Simerics.exe CP_nq31.spro -saveAs CP_nq31
    time_start = time.time()                                                                        # Set start timer 
    startupinfo = subprocess.STARTUPINFO()                                                          # Configure startupinfo for Simerics run without solver pop-up windows
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = subprocess.SW_HIDE
    print(' '.join(SMP_Cli))
    SMP_Run = subprocess.Popen(' '.join(SMP_Cli), startupinfo=startupinfo)                          # Run Simerics process 
    SMP_Run.wait()                                                                                  # Wait for process to finish
    time_elapsed = Print_Runtime(time_start)                                                        # Return Simerics solver wall clock time
    return time_elapsed

def Create_SPRO(baseName):                                                                          # Function to create spro files based on different batch variable values from the INI file structure
    modify_spro(baseName + '.spro')  
    baseName_List = []                                                                              # Create empty list that will be filled with file names containing basename + operation point
    if Get_ConfigValue('PreProcessing','batchVarData').lower() == 'relative':                       # Check if batchVar_ValuesAbs represent relative or absolute values, if relative values: convert to absolute values
        with open(baseName + '.spro','r') as infile:                                                # Get reference value of batch variable from spro file 
            for line in infile:                                                                     # Parse spro file line by line
                if (batchVar_Name + " = ") in line:                                                 # Search for expression for batch_VarName
                    batchVar_DesignPoint = line.split(" ")[-1]                                      # Retrieve original batch variable value
                    break                                                                           # Exit Loop
            batchVar_ValuesAbs = [Decimal(i)*Decimal(batchVar_DesignPoint) for i in batchVar_Values]# Convert relative values in batchVar_ValuesAbs to absolute values                                                               
    for item in batchVar_ValuesAbs:                                                                 # Loop over absolute batchVar_ValuesAbs which are operation points for batchVar
        baseName_Item = baseName + '_' + str(item)
        baseName_List.append(baseName_Item)                                                         # Create base names for new spro files, put the into a list object
        with open(baseName + '.spro','r') as infile, open(baseName_Item + '.spro','w') as outfile:  # Replace original batch variable value in the spro file with the new value, write the new spro file
            for line in infile:                                                                     # Parse spro file line by line
                if (batchVar_Name + " = ") in line:                                                 # Search for expression for batch_VarName
                    outfile.write("\t" + batchVar_Name + " = " + str(item) + "\n")                  # Replace expression for batch_VarName
                else:
                    outfile.write(line)                                                             # If not match batch_VarName expression just write the unmodfied line 
    return baseName_List, batchVar_ValuesAbs

def Get_FlowQuantityDescription(baseName):
    flowQOI = [item for item in Get_ConfigValue('PostProcessing','FlowQuantities').split(" ")]
    flowQOI_Dict = {}
    with open(baseName + '.spro','r') as infile:                                                    # Get reference value of batch variable from spro file 
        for line in infile:                                                                         # Parse spro file line by line
            for item in flowQOI:
                if ("#plot.%s:"%item) in line:                                                      # Search for expression for batch_VarName
                    flowQOI_Dict[item] = line.split(":")[-1]                                        # Retrieve original batch variable value
    print(flowQOI, flowQOI_Dict)
    return flowQOI, flowQOI_Dict

def Eval_Results(baseName, baseName_Item, baseName_Index, baseName_List, batchVar_ValuesAbs, avgWindow, analysis, time_elapsed):   # Function that evaluates and averages the userdefined expressions in the spro file after the CFD run
    result_Dict = {}                                                                                # Create a dictionary that will contain all the averaged values from a CFD run
    with open (baseName_Item + '_integrals.txt','r') as infile:                                     # Open _integrals.txt after Simerics solver run
        result_List = list(infile)                                                                  # Put results in list 
        del result_List[1:-avgWindow]                                                               # Delete everything in result list except the header row and the last n rows that will be used for averaging
        reader = csv.DictReader(result_List, delimiter="\t")                                        # Put data set in reader DictReader object, every row will be it's own dictionary
        for row in reader:                                                                          # Write values for batch variable and userdefined expressions in resultDict and average them
            if batchVar_Name in result_Dict:                                                        # Search for batchVar_Name in result_Dict
                result_Dict[batchVar_Name] += Decimal(batchVar_ValuesAbs[baseName_Index])           # Search for batchVar_Name in result_Dict, if exists, add value to existing value
            else:
                result_Dict[batchVar_Name] = Decimal(batchVar_ValuesAbs[baseName_Index])            # Search for batchVar_Name in result_Dict, if not exists, set key value to batchVar_Name value
            for key, value in row.items():
                if 'userdef.' in key:                                                               # Search for userdef expressions in result_Dict
                    if key in result_Dict:                                                           
                        result_Dict[key] += Decimal(value)                                          # Search for userdef expressions in result_Dict, if exists, add value to existing value        
                    else:
                        result_Dict[key] = Decimal(value)                                           # Search for userdef expressions in result_Dict, if not exists, set key value to userdef value
            if 'WallClockTime' in result_Dict:                                                      # Search for batchVar_Name in result_Dict
                result_Dict['WallClockTime'] += Decimal(time_elapsed)                               # Search for batchVar_Name in result_Dict, if exists, add value to existing value
            else:
                result_Dict['WallClockTime'] = Decimal(time_elapsed)                                # Search for batchVar_Name in result_Dict, if not exists, set key value to batchVar_Name value
        for key,value in result_Dict.items():
              result_Dict[key] = result_Dict[key] / Decimal(avgWindow)                              # Average values in result_Dict
    with open (baseName + '_integrals.csv','a+',newline='') as outfile:                             
        writer = csv.DictWriter(outfile, fieldnames=result_Dict.keys(), delimiter="\t")             # Use DictWriter to write averaged results from result_Dict in CSV file
        if baseName_Index == 0:                                                          
            writer.writeheader()                                                                    # For first CFD run also write a header row, after that, don't
        writer.writerow(result_Dict)
    Write_HTML(baseName, result_Dict, baseName_Index, baseName_List, analysis)
    
def Run_CFD(analysis, SteadyState):                                                                 # Function that calls the CFD solver
    baseName = Get_ConfigValue(analysis,'BaseName')                                                 # Get base name for CFD run, depends on steady-state or transient CFD run
    avgWindow = int(Get_ConfigValue(analysis,'AveragingWindow'))                                    # Get averaging window for post-processing, depends on steady-state or transient
    if Get_ConfigValue('PreProcessing','MeshGeometry').lower() == 'true':                           # Run meshing function if meshing was enabled in the INI file structure
        SMP_Args = [baseName + '.spro', "-saveAs", baseName]                                        # Create arguments for meshing run
        SMP_Solver(SMP_Args)                                                                        # Start Simerics meshing run
    baseName_List, batchVar_ValuesAbs = Create_SPRO(baseName)                                       # Call function to create spro files, this should be done after the meshing otherwise the mesh will be re-created on every solver
    for baseName_Index, baseName_Item in enumerate(baseName_List):                                  # Iterate through list with all operation points
        SMP_Args = ["-run", baseName_Item + '.spro']                                                # Create arguments for solver run
        if analysis == 'steady' and baseName_Index != 0:                                            # Continue from previous CFD results if run is steady-state analysis and not first solver run
            SMP_Args.append(baseName_List[baseName_Index - 1] + '.sres')                            # Append arguments to start from previous steady-state CFD result
        elif analysis == 'transient':                                                               # Start from steady-state solution if analysis type is transient
            SMP_Args.append(SteadyState[baseName_Index] + '.sres')                                  # Append arguments to start from steady-state CFD result
        time_elapsed = SMP_Solver(SMP_Args)                                                                      # Start Simerics solver run
        Eval_Results(baseName, baseName_Item, baseName_Index, baseName_List, batchVar_ValuesAbs, avgWindow, analysis, time_elapsed)
    return baseName_List

def Write_HTML(baseName, result_Dict, baseName_Index, baseName_List, analysis):                     # Function that fills the results.html
    HTML_Dict = {}
    with open (baseName + '_integrals.csv','r') as infile:
        reader = csv.DictReader(infile, delimiter="\t")
        for row in reader:
            for item in flowQuantities:
                if item not in HTML_Dict:
                    HTML_Dict[item] = []
                HTML_Dict[item].append(row[item])
            if batchVar_Name not in HTML_Dict:
                HTML_Dict[batchVar_Name] = []
            HTML_Dict[batchVar_Name].append(row[batchVar_Name])
    HTML_infile = '__results.html'
    HTML_outfile = '__results.html'
    with open(HTML_infile, 'r') as infile: 
        output = []
        for line in infile.readlines():
            if "_NAME" in line:
                flowQOI, flowQOI_Dict = Get_FlowQuantityDescription(baseName) 
                for index,item in enumerate(flowQOI):
                    if ("QOI_%s_NAME" % str(index + 1)) in line:
                        output.append("            <h1>%s</h1>" %item + "\n")
            elif "_DESCRIPTION" in line:
                flowQOI, flowQOI_Dict = Get_FlowQuantityDescription(baseName) 
                for index,item in enumerate(flowQOI):
                    if ("QOI_%s_DESCRIPTION" % str(index+1)) in line:
                        output.append("            <h2>%s</h2>" %flowQOI_Dict[item] + "\n")                
            elif "<h1>SIMULATION NOT STARTED</h1>" in line:
                output.append("			<h1>SIMULATION RUNNING ...</h1>" + "\n")
            elif "    var QOI_" in line and analysis in line:
                for index,item in enumerate(flowQuantities):
                    if (str(index + 1) + "_" + analysis + " = ") in line:
                        output.append("    var QOI_" + str(index+1) + "_" + analysis + " = " + str(HTML_Dict[item]) + "\n")
            elif ("    var batchVarName = ") in line and analysis == 'steady':
                output.append("    var batchVarName = " + str(HTML_Dict[batchVar_Name]) + ";\n")
            elif ((analysis == 'steady' and Get_ConfigValue('PreProcessing','runTransient').lower() == 'false') or (analysis == 'transient' and Get_ConfigValue('PreProcessing','runTransient').lower() == 'true')) and (baseName_Index == (len(baseName_List) - 1)):
                if "<h1>SIMULATION RUNNING ...</h1>" in line:
                    output.append("			<h1>SIMULATION FINISHED</h1>" + "\n")
                elif "		<meta http-equiv" in line:
                    output.append("		<meta >" + "\n")
                else:
                    output.append(line)
            else:
                output.append(line)
    with open(HTML_outfile, 'w') as outfile:
        for line in output:
            outfile.write(line)

def main():
    
    time_start = time.time()                                                                        # Set start timer for whole all CFD runs       
    
    if Get_ConfigValue('PreProcessing','runTransient').lower() == 'true':                           # Check if transient run is configured
        BaseNameListSteady = Run_CFD('steady', SteadyState=None)                                     # Run steady-state analysis first, get list with basenames that contain operation points (will be used for .sres file names)
        Run_CFD('transient', BaseNameListSteady)                                                     # Run transient analysis                       
    else:
        Run_CFD('steady', SteadyState=None)                                                          # Run steady-state analysis
    
    Print_Runtime(time_start)

main()
input("Press Enter to continue")
