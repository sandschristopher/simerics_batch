import numpy as np
from shutil import copy, copyfile
import configparser
import csv
import decimal
from decimal import Decimal
import os
import subprocess
import time
from re import search
from __modify_spro import *

def Get_ConfigValue(ConfigSection, ConfigKey):                                                      # Function to retrieve values from the INI file structure
    ConfigValue = CFconfig[ConfigSection][ConfigKey]
    return ConfigValue

CFconfig = configparser.ConfigParser()                                                              # Initialize Config
CFconfig.read('__Runconfig.cftconf')                                                                # Read Config
batchVar1_Name = Get_ConfigValue('PreProcessing','rpm')                                         # Get name of batch variable
batchVar1_Values = Get_ConfigValue('PreProcessing','rpmValues').split(" ")                      # Get values for batch variable, format the as a list by splitting
batchVar2_Name = Get_ConfigValue('PreProcessing','flowRate')   
batchVar2_Values = Get_ConfigValue('PreProcessing','flowRateValues').split(" ") 
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

def Create_SPRO(baseName, stage_components):                                                        # Function to create spro files based on different batch variable values from the INI file structure
    modify_spro(baseName + '.spro', stage_components)  
    baseName_List = []                                                                              # Create empty list that will be filled with file names containing basename + operation point
    if Get_ConfigValue('PreProcessing', 'rpmData').lower() == 'relative':                     # Check if batchVar1_ValuesAbs represent relative or absolute values, if relative values: convert to absolute values
        with open(baseName + '.spro', 'r') as infile:                                               # Get reference value of batch variable from spro file 
            for line in infile:                                                                     # Parse spro file line by line
                if batchVar1_Name in line and " = " in line:                                                # Search for expression for batch_VarName
                    batchVar1_DesignPoint = line.split(" ")[-1]                                     # Retrieve original batch variable value
                    # impeller_Number = search("Omega(\d) = ", line).group(1)
                    break
            batchVar1_ValuesAbs = [Decimal(_)*Decimal(batchVar1_DesignPoint) for _ in batchVar1_Values]# Convert relative values in batchVar1_ValuesAbs to absolute values                                                               
    if Get_ConfigValue('PreProcessing', 'flowRateData').lower() == 'relative':
        with open(baseName + '.spro', 'r') as infile: 
            for line in infile: 
                if (batchVar2_Name + " = ") in line:
                    batchVar2_DesignPoint = line.split(" ")[-1]  
            batchVar2_ValueAbs = [Decimal(i)*Decimal(batchVar2_DesignPoint) for i in batchVar2_Values]
    baseName_Array = np.empty((len(batchVar1_ValuesAbs), len(batchVar2_ValueAbs)), dtype=object)
    for index1, item1 in enumerate(batchVar1_ValuesAbs):                                                                 # Loop over absolute batchVar1_ValuesAbs which are operation points for batchVar1
        for index2, item2 in enumerate(batchVar2_ValueAbs):
            baseName_Item = baseName + '_' + str(round(item1*Decimal(9.5492))) + 'rpm_' +  str(item2) + "m3s"
            baseName_Array[index1][index2] = baseName_Item 
            baseName_List.append(baseName_Item)                                                         # Create base names for new spro files, put the into a list object
            with open(baseName + '.spro','r') as infile, open(baseName_Item + '.spro','w') as outfile:  # Replace original batch variable value in the spro file with the new value, write the new spro file
                for line in infile:                                                                     # Parse spro file line by line
                    if (batchVar1_Name + " = ") in line:                                                 # Search for expression for batch_VarName
                        outfile.write("\t\t" + batchVar1_Name + " = " + str(item1) + "\n")                  # Replace expression for batch_VarName
                    elif (batchVar2_Name + " = ") in line:
                        outfile.write("\t\t" + batchVar2_Name + " = " + str(item2) + "\n") 
                    else:
                        outfile.write(line)                                                             # If not match batch_VarName expression just write the unmodfied line 
    return baseName_Array, batchVar1_ValuesAbs, batchVar2_ValueAbs

def Get_FlowQuantityDescription(baseName):
    flowQOI = [item for item in Get_ConfigValue('PostProcessing','FlowQuantities').split(" ")]
    flowQOI_Dict = {}
    with open(baseName + '.spro','r') as infile:                                                    # Get reference value of batch variable from spro file 
        for line in infile:                                                                         # Parse spro file line by line
            if "#plot.PC" in line:
                impeller_Number = search("#plot.PC(\d):", line).group(1)
                for index, item in enumerate(flowQOI):
                    if "PC" in item:
                        flowQOI[index] = "PC" + impeller_Number
            for item in flowQOI:
                if ("#plot.%s:"%item) in line:                                                      # Search for expression for batch_VarName
                    flowQOI_Dict[item] = line.split(":")[-1]                                        # Retrieve original batch variable value
    return flowQOI, flowQOI_Dict

def Eval_Results(baseName, baseName_Item, baseName_Index, baseName_Row, baseName_Array, batchVar1_ValuesAbs, batchVar2_ValuesAbs, avgWindow, analysis, time_elapsed):   # Function that evaluates and averages the userdefined expressions in the spro file after the CFD run                                                                              # Create a dictionary that will contain all the averaged values from a CFD run
    result_Dict = {}
    with open (baseName_Item + '_integrals.txt','r') as infile:                                     # Open _integrals.txt after Simerics solver run
        result_List = list(infile)                                                                  # Put results in list 
        del result_List[1:-avgWindow]                                                               # Delete everything in result list except the header row and the last n rows that will be used for averaging
        reader = csv.DictReader(result_List, delimiter="\t")                                        # Put data set in reader DictReader object, every row will be it's own dictionary
        result_Dict[batchVar1_Name] = Decimal(batchVar1_ValuesAbs[baseName_Row]) 
        result_Dict[batchVar2_Name] = Decimal(batchVar2_ValuesAbs[baseName_Index])  
        for row in reader:                                                                          # Write values for batch variable and userdefined expressions in resultDict and average them
            for key, value in row.items():
                if 'userdef.' in key:                                                               # Search for userdef expressions in result_Dict
                    if key in result_Dict:                                                           
                        result_Dict[key] += Decimal(value)                                          # Search for userdef expressions in result_Dict, if exists, add value to existing value        
                    else:
                        result_Dict[key] = Decimal(value)                                           # Search for userdef expressions in result_Dict, if not exists, set key value to userdef value
        result_Dict['WallClockTime'] = Decimal(time_elapsed)                                # Search for batchVar1_Name in result_Dict, if not exists, set key value to batchVar1_Name value
        for key, value in result_Dict.items():
            if key != batchVar1_Name and key != batchVar2_Name and key != 'WallClockTime':
                result_Dict[key] = result_Dict[key] / Decimal(avgWindow)                              # Average values in result_Dict
    with open (baseName + '_integrals.csv', 'a+', newline='') as outfile:                             
        writer = csv.DictWriter(outfile, fieldnames=result_Dict.keys(), delimiter=",")              # Use DictWriter to write averaged results from result_Dict in CSV file
        if baseName_Item == baseName_Array[0][0]:                                                        
            outfile.truncate(0)
            writer.writeheader()                                                                    # For first CFD run also write a header row, after that, don't
        writer.writerow(result_Dict)
    Write_HTML(baseName, baseName_Item, baseName_Index, baseName_Row, baseName_Array, batchVar1_ValuesAbs, batchVar2_ValuesAbs, result_Dict, analysis)
        
def Run_CFD(analysis, stage_components, SteadyState):                                               # Function that calls the CFD solver
    baseName = Get_ConfigValue(analysis, 'BaseName')                                                # Get base name for CFD run, depends on steady-state or transient CFD run
    avgWindow = int(Get_ConfigValue(analysis, 'AveragingWindow'))                                   # Get averaging window for post-processing, depends on steady-state or transient
    SMP_Solver([' -save ', baseName + '.spro'])
    if Get_ConfigValue('PreProcessing', 'MeshGeometry').lower() == 'true':                          # Run meshing function if meshing was enabled in the INI file structure
        SMP_Args = [baseName + '.spro', ' -saveAs', baseName]                                       # Create arguments for meshing run
        SMP_Solver(SMP_Args)                                                                        # Start Simerics meshing run
    baseName_Array, batchVar1_ValuesAbs, batchVar2_ValuesAbs = Create_SPRO(baseName, stage_components)                     # Call function to create spro files, this should be done after the meshing otherwise the mesh will be re-created on every solver
    for baseName_Row, row in enumerate(baseName_Array):
        for baseName_Index, baseName_Item in enumerate(row):                                            # Iterate through list with all operation points
            SMP_Args = ["-run ", baseName_Item + '.spro']                                               # Create arguments for solver run
            if analysis == 'steady' and baseName_Index != 0:                                            # Continue from previous CFD results if run is steady-state analysis and not first solver run
                SMP_Args.append(row[baseName_Index - 1] + '.sres')                                      # Append arguments to start from previous steady-state CFD result
            elif analysis == 'transient':                                                               # Start from steady-state solution if analysis type is transient
                SMP_Args.append(row[baseName_Index].replace("transient", "steady") + '.sres')           # Append arguments to start from steady-state CFD result
            time_elapsed = SMP_Solver(SMP_Args)                                                         # Start Simerics solver run
            Eval_Results(baseName, baseName_Item, baseName_Index, baseName_Row, baseName_Array, batchVar1_ValuesAbs, batchVar2_ValuesAbs, avgWindow, analysis, time_elapsed)
    return baseName_Array


def Write_HTML(baseName, baseName_Item, baseName_Index, baseName_Row, baseName_Array, batchVar1_ValuesAbs, batchVar2_ValuesAbs, result_Dict, analysis):                     # Function that fills the results.html

    flowQOI = Get_FlowQuantityDescription(baseName)[0]
    HTML_flowQOI = ['userdef.' + item for item in Get_FlowQuantityDescription(baseName)[0]]


    name = str(baseName.split("_")[0] + "_" + baseName.split("_")[1])

    if baseName_Item == baseName_Array[0][0] and analysis == analysis == 'steady':
        with open ('__results.html','r') as infile, open('__' + name + '_results.html','w') as outfile:
            data = infile.readlines()
            for line_number, line in enumerate(data):
                if "var batchVarName = [];" in line:
                    outfile.write(line)
                    index = line_number
                    for i in range(len(flowQOI)):
                        for j in range(baseName_Array.shape[0]):
                            index += 1
                            data.insert(index, "\n\t\t" + "var QOI_" + str(i + 1) + "_steady" + str(j + 1) + " = [];" + "\n\t\t" + "var QOI_" + str(i + 1) + "_transient" + str(j + 1) + " = [];")
                
                elif "data: QOI_" in line and "steady1" in line:
                    outfile.write(line)
                    template = data[line_number - 1: line_number + 11]
                    index = line_number - 1
                    for j in range(1, baseName_Array.shape[0]):
                        index += 12
                        new = [item.replace("steady1", "steady" + str(j + 1)) for item in template]
                        new = [item.replace("transient1", "transient" + str(j + 1)) for item in new]
                        new = [item.replace("}\n", "},\n") for item in new]
                        for i, item in enumerate(new):
                            if i == len(new) - 1 and j == baseName_Array.shape[0] - 1:
                                data.insert(index + i, item.replace("},", "}"))
                            else:
                                data.insert(index + i, item)
                        
                else:
                    outfile.write(line)

    if baseName_Array.shape[0] > 1 and baseName_Item == baseName_Array[0][0] and analysis == 'steady':
        with open('__' + name + '_results.html','r') as infile:
            data = infile.readlines()
            for line_number, line in enumerate(data):
                if "data: QOI_" in line and "_transient1" in line:
                    data[line_number + 4] = data[line_number + 4].replace("}", "},")

        with open('__' + name + '_results.html','w') as outfile:
            outfile.writelines(data)

    HTML_Dict = {}

    with open (baseName + '_integrals.csv','r') as infile:
        reader = csv.DictReader(infile, delimiter=",")
        for row in reader:
            if row[batchVar1_Name] == str(batchVar1_ValuesAbs[baseName_Row]):
                for item in HTML_flowQOI:
                    if item not in HTML_Dict:
                        HTML_Dict[item] = []
                    HTML_Dict[item].append(row[item])
                if batchVar1_Name not in HTML_Dict:
                    HTML_Dict[batchVar1_Name] = []
                HTML_Dict[batchVar1_Name].append(row[batchVar1_Name])
                if batchVar2_Name not in HTML_Dict:
                    HTML_Dict[batchVar2_Name] = []
                HTML_Dict[batchVar2_Name].append(row[batchVar2_Name])
    
    HTML_infile = '__' + name + '_results.html'
    HTML_outfile = '__' + name + '_results.html'

    with open(HTML_infile, 'r') as infile: 
        output = []
        for line in infile.readlines():
            if "_NAME" in line:
                flowQOI, flowQOI_Dict = Get_FlowQuantityDescription(baseName) 
                for index, item in enumerate(flowQOI):
                    if ("QOI_%s_NAME" % str(index + 1)) in line:
                        output.append("            <h1>%s</h1>" %item + "\n")
            elif "_DESCRIPTION" in line:
                flowQOI, flowQOI_Dict = Get_FlowQuantityDescription(baseName) 
                for index, item in enumerate(flowQOI):
                    if ("QOI_%s_DESCRIPTION" % str(index + 1)) in line:
                        output.append("            <h2>%s</h2>" %flowQOI_Dict[item] + "\n")                
            elif "<h1>SIMULATION NOT STARTED</h1>" in line:
                output.append("			<h1>SIMULATION RUNNING ...</h1>" + "\n")
            elif "var QOI_" in line and analysis + str(baseName_Row + 1) in line:
                for index, item in enumerate(HTML_flowQOI):
                    if (str(index + 1) + "_" + analysis + str(baseName_Row + 1) + " = ") in line:
                        output.append("\t\tvar QOI_" + str(index + 1) + "_" + analysis +  str(baseName_Row + 1) + " = " + str(HTML_Dict[item]) + ";\n")
            elif ("var batchVarName = ") in line and analysis == 'steady' and baseName_Row == 0:
                output.append("\t\tvar batchVarName = " + str(HTML_Dict[batchVar2_Name]) + ";\n")
            elif ((analysis == 'steady' and Get_ConfigValue('PreProcessing','runTransient').lower() == 'false') or (analysis == 'transient' and Get_ConfigValue('PreProcessing','runTransient').lower() == 'true')) and (baseName_Item == baseName_Array.flat[-1]):
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

    stage_components = []
    stage_components.append(int(input("Enter the number associated with the initial stage component: ")))
    stage_components.append(int(input("Enter the number associated with the final stage component: ")))
    
    time_start = time.time()                                                                         # Set start timer for whole all CFD runs       
    
    if Get_ConfigValue('PreProcessing', 'runTransient').lower() == 'true':                           # Check if transient run is configured
        BaseNameListSteady = Run_CFD('steady', stage_components, SteadyState=None)                   # Run steady-state analysis first, get list with basenames that contain operation points (will be used for .sres file names)
        Run_CFD('transient', stage_components, BaseNameListSteady)                                   # Run transient analysis                       
    else:
        Run_CFD('steady', stage_components, SteadyState=None)                                        # Run steady-state analysis
    
    Print_Runtime(time_start)

main()
input("Press Enter to continue")