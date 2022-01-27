from re import search

def modify_spro(spro_file, stage_components):

    # Gets the mismatched grid interface names.
    MGIs = []
    with open(spro_file, 'r') as infile:
        for line in infile.readlines():
            if "patch=\"MGI" in line:
                MGIs.append(line.strip().split("\"")[1])

    # Gets the interface names for each control volume:
    CVs = list(MGIs)
    with open(spro_file, 'r') as infile:
        for line in infile.readlines():
            if "plot.DPtt = " in line:
                CVs.insert(0, line.split("\"")[3])
                CVs.append(line.split("\"")[1])

    # Gets the total number of components:
    num_components = len(MGIs) + 1

    # Gets number associated with the impeller:
    with open(spro_file, 'r') as infile:
        for line in infile.readlines():
            if "Omega" in line:
                impeller_number = line.split("=")[0].strip()[-1]
                break

    # Gets name associated with the rotating component:
    with open(spro_file, 'r') as infile:
        for line in infile.readlines():
            if "plot.PC"  in line:
                impeller_name = line.split("\"")[1].split("-")[0].strip()
                break

    # Gets value of fluid density:
    with open(spro_file, 'r') as infile:
        for line in infile.readlines():
            if "rho =" in line:
                density = float(line.split("=")[1].strip())

    # Gets name of leakage interface:
    with open(spro_file, 'r') as infile:
        for line in infile.readlines():
            if "OutletInterface" in line:
                leakage_interface = line.split("\"")[1].strip()
            else:
                leakage_interface = 0

    with open(spro_file, 'r') as infile:
        for line in infile.readlines():
            if "#Outlet" in line:
                indent = " " * (len(line) - len(line.lstrip(" ")))
                break
     
    # Ensure grid file consistency between steady-state and transient simulations
    with open(spro_file, 'r') as infile:
        data = infile.readlines()
        for line_number, line in enumerate(data):
            if ".sgrd" in line:
                data[line_number] = line.replace("transient", "steady")
                break
     
    with open(spro_file, 'w') as outfile:
        data = "".join(data)
        outfile.write(data)
        
    
    def insert_line(addition):

        exists_already = False

        with open(spro_file, 'r') as infile:
            data = infile.readlines()
            for line_number, line in enumerate(data):
                if addition.split("\n")[0].strip() in line:
                    exists_already = True
                    
        if exists_already == False:
            with open(spro_file, 'r') as infile:
                data = infile.readlines()
                for line_number, line in enumerate(data):
                    if "</expressions>" in line:
                        data.insert(line_number, "\n" + addition + "\n")
                        break

            with open(spro_file, 'w') as outfile:
                data = "".join(data)
                outfile.write(data)

    insert_line(indent + "#head [m]" + "\n" + indent + "plot.H = plot.DPtt/rho/9.81 \n" + indent + "#plot.H:head [m]")

    insert_line(indent + "#head, imp1 [m]" + "\n" + indent + "plot.H = plot.DPtt" + impeller_number + "/rho/9.81 \n" + indent + "#plot.H:head, imp1 [m]")
    
    insert_line(indent + "#delta p (t-t), stage [Pa]" + "\n" + indent + "plot.DPtt_stage = flow.mpt@\"" \
        + CVs[stage_components[-1]] + "\" - flow.mpt@\"" + CVs[(stage_components[0] - 1)] + "\"\n" + indent + "#plot.DPtt_stage:delta p (t-t), stage [Pa]")
    
    insert_line(indent + "#efficiency (t-t), stage [-]" + "\n" + indent + "plot.Eff_tt_stage = flow.q@\"" \
        + CVs[stage_components[-1]] + "\"*plot.DPtt_stage/rho/plot.PC" + impeller_number + "\n" + indent + "#plot.Eff_tt_stage:efficiency (t-t), stage [-]")

    for i in range(1, len(CVs)):
        insert_line(indent + "#delta p (t-t), CV" + str(i) + " [Pa]" + "\n" + indent + "plot.DPttCV" + str(i) + " = flow.mpt@\"" \
            + CVs[i] + "\" - flow.mpt@\"" + CVs[i - 1] + "\"\n" + indent + "#plot.DPttCV" + str(i) + ":delta p (t-t), CV" \
            + str(i) + " [Pa]")

        insert_line(indent + "#delta p (t-s), CV" + str(i) + " [Pa]" + "\n" + indent + "plot.DPtsCV" + str(i) + " = flow.p@\"" \
            + CVs[i] + "\" - flow.p@\"" + CVs[i - 1] + "\"\n" + indent + "#plot.DPtsCV" + str(i) + ":delta p (t-s), CV" \
            + str(i) + " [Pa]")

    if leakage_interface != 0:

        insert_line(indent + "#mass flow, shroud leakage, relative [-]" + "\n" + indent + "plot.mShroudLeakageRel = (flow.q@\"" \
            + leakage_interface + "\" - flow.q@\"" + CVs[-1] + "\")/(flow.q@\"" + CVs[-1] + "\")" + "\n" + indent + "#plot.mShroudLeakageRel:mass flow, shroud leakage, relative [-]")

        insert_line(indent + "#mass flow, shroud leakage, absolute [kg/s]" + "\n" + indent + "plot.mShroudLeakageAbs = flow.q@\"" \
            + leakage_interface + "\" - flow.q@\"" + CVs[-1] + "\"\n" + indent + "#plot.mShroudLeakageAbs:mass flow, shroud leakage, absolute [kg/s]")

        insert_line(indent + "#volumetric flow, shroud leakage, relative [-]" + "\n" + indent + "plot.vShroudLeakageRel = (flow.qv@\"" \
            + leakage_interface + "\" - flow.qv@\"" + CVs[-1] + "\")/(flow.qv@\"" + CVs[-1] + "\")" + "\n" + indent + "#plot.vShroudLeakageRel:volumetric flow, shroud leakage, relative [-]")

        insert_line(indent + "#volumetric flow, shroud leakage, absolute [m3/s]" + "\n" + indent + "plot.vShroudLeakageAbs = flow.qv@\"" \
            + leakage_interface + "\" - flow.qv@\"" + CVs[-1] + "\"\n" + indent + "#plot.vShroudLeakageAbs:volumetric flow, shroud leakage, absolute [m3/s]")

        insert_line(indent + "#efficiency (t-t), imp1 passage [-]" + "\n" + indent + "plot.Eff_tt_" + impeller_number + "Passage = flow.qv@\"" \
            + leakage_interface + "\"*plot.DPtt" + impeller_number + "Passage/plot.PC" + impeller_number + "Passage" + "\n" + indent + "#plot.Eff_tt_" + impeller_number + "Passage:efficiency (t-t), imp1 passage [-]")

        insert_line(indent + "#power, imp1 passage [W]" + "\n" + indent + "plot.PC" + impeller_number + "Passage = abs(flow.power@\"" + impeller_name + "-Hub\"" \
            + " + flow.power@\"" + impeller_name + "-Shroud\" + flow.power@\"" + impeller_name + "-BladeSides\" + flow.power@\"" + impeller_name + "-BladeLE\" + flow.power@\"" + impeller_name + "-BladeTE\")" \
            + "\n" + indent + "#plot.PC" + impeller_number + "Passage:power, imp1 passage [W]")

        insert_line(indent + "#delta p (t-t), imp1 passage [Pa]" + "\n" + indent + "plot.DPtt2Passage = flow.mpt@\"" \
            + leakage_interface + "\" - flow.mpt@\"" + MGIs[0] + "\"\n" + indent + "#plot.DPtt2Passage:delta p (t-t), imp1 passage [Pa]")

        insert_line(indent + "#volumetric flow, OutletInterface, absolute [m3/s]" + "\n" + indent + "plot.vOutletInterface = flow.qv@\"" \
            + leakage_interface + "\"\n" + indent + "#plot.vOutletInterface:#volumetric flow, OutletInterface, absolute [m3/s]")

        insert_line(indent + "#volumetric flow, OutletExtension, absolute [m3/s]" + "\n" + indent + "plot.vOutletExtension = flow.qv@\"" \
            + CVs[-1] + "\"\n" + indent + "#plot.vOutletExtension:#volumetric flow, OutletExtension, absolute [m3/s]")

    with open(spro_file, "r") as infile:
        units_Dict = {}
        desc_Dict = {}
        data = infile.readlines()
        for line in data:
            if "#plot." in line:
                key = line.split(":")[0].split(".")[1].strip()
                if key == "DPtt" + impeller_number:
                    key = "DPtt_imp"
                if key == "Eff_tt_" + impeller_number + "_i":
                    key = "Eff_tt_imp"
                units_Dict[key] = line.split(" ")[-1].strip() 
                desc_Dict[key] = line.split("[")[0].split(":")[1].strip()

    return units_Dict, desc_Dict
