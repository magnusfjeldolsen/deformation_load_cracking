import os
import re
import json
import numpy as np
import pandas as pd
import sys
import importlib.util
import subprocess
import openpyxl
import docx


#This script converts output from FEM-design to a .xlsx adapted
#for input to MULTICON

#Merging of dataframes are passed sort=False to deal with future behaviour of dataframes

def getLoadCasesDataFrame(xlsx_path):
    #Getting dataframe containing names of load cases
    pd_xlsx=pd.ExcelFile(xlsx_path)

    for sheet in pd_xlsx.sheet_names:
        if "Load cases" in sheet:
            df_load_cases = pd.ExcelFile.parse(pd_xlsx,sheet,skiprows=1)

    #renameing "Name" column to "load_case" to match output of other functions
    df_load_cases=df_load_cases.rename(columns={"Name":"load_case"})

    return df_load_cases

def getLoadCaseName(xlsx_path,sheet):
    #Get name of load case from cell A1 in FEM-design export

    ####OLD CODE, xlrd is outdated
    #workbook=xlrd.open_workbook(xlsx_path)
    #worksheet=workbook.sheet_by_name(sheet)
    #load_case_string_raw=str(worksheet.cell(0,0).value)


    ####NEW CODE
    workbook=openpyxl.load_workbook(xlsx_path)
    worksheet=workbook[sheet]
    load_case_string_raw=str(worksheet["A1"].value)
    load_case=load_case_string_raw.split(": ")[-1]

    return load_case

def fillMissingStringsInDataFrame(df,column_name):
    #A function that fills inn empty rows in dataframe columns after occuring string values
    #For instance, when "fill all cells" is not selected in FEM-design export

    #converting column to list
    id_list = df[column_name].tolist()
    for idx,item in enumerate(id_list):
        if isinstance(item,str):
            id_string = item
        else:
            id_list[idx]=id_string
    
    df[column_name]=id_list
    return df

def getNLargestSigma1(df_sigma_1,n=1):
    #Returning n largest sigma 1 of each shell
    df_sigma_1["Sigma 1"] = df_sigma_1["Sigma 1"].astype(float)

    df_sigma_1_largest=df_sigma_1.groupby("ID").apply(lambda x: x.nlargest(n,"Sigma 1")).reset_index(drop=True)

    #sorting dataframe by largest to smallest value of Sigma 1
    df_sigma_1_largest=df_sigma_1_largest.sort_values(by=["Sigma 1"])

    return df_sigma_1_largest

def getShellStressesDataFrame(xlsx_path,n_largest=1):
    #Reading entire workbook by xlsx_path into 
    pd_xlsx=pd.ExcelFile(xlsx_path)
    sigma_1_list=[]
    

    for sheet in pd_xlsx.sheet_names:
        df_sheet = pd.ExcelFile.parse(pd_xlsx,sheet,skiprows=1)
        
        if "Shells, Stresses, top" in sheet:
            #Getting sheet into a dataframe
            load_case = getLoadCaseName(xlsx_path,sheet)    
            df_sheet["load_case"]=load_case
            sigma_1_list.append(df_sheet)
            
        elif "Shells, Stresses, bottom" in sheet:
            load_case = getLoadCaseName(xlsx_path,sheet)
            df_sheet["load_case"]=load_case
            sigma_1_list.append(df_sheet)

    df_sigma_1 = pd.concat(sigma_1_list,ignore_index=True,sort=False)
    #Removing rows where Sigma 1 is not a number
    df_sigma_1 = df_sigma_1[pd.to_numeric(df_sigma_1["Sigma 1"], errors = "coerce").notnull()]
    df_sigma_1=df_sigma_1.rename({"Shell":"ID"},axis=1)

    #Inserting missing ID-values
    df_sigma_1=fillMissingStringsInDataFrame(df_sigma_1,"ID")
    #Filtering out n largest sigma 1 if specified
    if n_largest is not None:
        df_sigma_1 = getNLargestSigma1(df_sigma_1,n=n_largest)
    del df_sheet

    return df_sigma_1

def getShellInternalForcesDataFrame(xlsx_path):
    #Reading entire workbook by xlsx_path into 
    pd_xlsx=pd.ExcelFile(xlsx_path)
    internal_forces_list=[]

    for sheet in pd_xlsx.sheet_names:
        df_sheet = pd.ExcelFile.parse(pd_xlsx,sheet,skiprows=1)
        
        if "Shells, Internal forces" in sheet:
            #Getting sheet into a dataframe
            load_case = getLoadCaseName(xlsx_path,sheet)
            df_sheet["load_case"]=load_case
            internal_forces_list.append(df_sheet)
        
    df_shell_internal_forces = pd.concat(internal_forces_list,ignore_index=True,sort=False)
    #Removing rows where Elem is not a number
    df_shell_internal_forces = df_shell_internal_forces[pd.to_numeric(df_shell_internal_forces["Elem"], errors = "coerce").notnull()]
    
    df_shell_internal_forces=fillMissingStringsInDataFrame(df_shell_internal_forces,"ID")
    return df_shell_internal_forces

def getAppliedReinforcement(xlsx_path):
    pd_xlsx=pd.ExcelFile(xlsx_path)
    applied_reinforcement_list=[]

    for sheet in pd_xlsx.sheet_names:
        df_sheet = pd.ExcelFile.parse(pd_xlsx,sheet,skiprows=1)
        
        if "Applied reinforce" in sheet:
            applied_reinforcement_list.append(df_sheet)
            
    df_applied_reinforcement = pd.concat(applied_reinforcement_list,ignore_index=True,sort=False)
    df_applied_reinforcement = df_applied_reinforcement[pd.to_numeric(df_applied_reinforcement["Elem"], errors = "coerce").notnull()]

    
    df_applied_reinforcement.drop(["ID","Node"],inplace=True,axis=1)
    #dropping "ID"-column beacuse FEM-design does not provide values in every row
    #for some currently unknow reason, Node also has to be dropped in order to merge with a dataframe of stresses and internal forces

    return df_applied_reinforcement

def proposeRebarDiameter(As,area_unit=r'cm2/m',test_diameters_list=None,test_cc_list=None):
    #As: Applied reinfocement area [mm2/m]
    #This function attempts to return rebar diameter given As

    if test_diameters_list ==None:
        D=[12,16,20,25,32]
    else:
        D=test_diameters_list
    
    if test_cc_list == None:
        S=[100,150,200,250]
    else:
        S=test_cc_list

    if area_unit==r'cm2/m':
        scale_area=0.01
    elif area_unit==r'mm2/m':
        scale_area=1
    else:
        scale_area = area_unit
        print(f"Scaling area mm2/m by a factor of {scale_area}")
    
    #initialize error
    error = None

    #loop through possible rebar size combinatinos
    for d in D:
        for s in S:
            Asi=np.pi*d**2/4*1000/s*scale_area
            if error == None:
                error = abs(As-Asi)
                candidate_diameter = d
                #candidate_cc=s
            elif abs(As-Asi)<error:
                error = abs(As-Asi) 
                candidate_diameter = d
                #candidate_cc=s

    #print(f"candidate_diameter:{candidate_diameter}")

    return candidate_diameter

def getWallsAndPlatesDataFrame(xlsx_path):
    pd_xlsx=pd.ExcelFile(xlsx_path)
    walls_and_plates_list=[]

    for sheet in pd_xlsx.sheet_names:
        df_sheet = pd.ExcelFile.parse(pd_xlsx,sheet,skiprows=1)

        if "Plates" in sheet or "Walls" in sheet:
            walls_and_plates_list.append(df_sheet)

    df_walls_and_plates = pd.concat(walls_and_plates_list,ignore_index=True,sort=False)
    #dropping rows with non-numeric thickness
    df_walls_and_plates = df_walls_and_plates[pd.to_numeric(df_walls_and_plates["t1"], errors = "coerce").notnull()]

    #keeping only the columns of interest - just ID and t1 variable thickness is not considered!
    df_walls_and_plates = df_walls_and_plates[["ID","t1"]] 
    
    return df_walls_and_plates
        
def mergeDataFrames(df_load_cases,df_sigma_1,df_shell_internal_forces,df_applied_reinforcement,df_walls_and_plates):
    #Merging df_sigma_1 and df_shell_internal_forces
    common_columns_stresses_forces = list(set(df_sigma_1.columns) & set(df_shell_internal_forces.columns))
    df = pd.merge(df_sigma_1,df_shell_internal_forces,on=["Elem"].append(common_columns_stresses_forces.remove("Elem")))

    #Merging df of stresses and forces with df_applied_reinforcement
    common_columns_df_applied_reinforcement = list(set(df.columns) & set(df_applied_reinforcement.columns))
    df = pd.merge(df,df_applied_reinforcement,on=["Elem"])#.append(common_columns_df_applied_reinforcement))#.remove("Elem")))
    
    #Merging df of stresses, forces and reinforcement with dataframe containting thickness
    df = pd.merge(df,df_walls_and_plates,on=["ID"])
    try:
        #if export from FEM-design was for selected objects, load_cases contains a 
        # - for selected objects, which has to be removed when merging with df_load_cases
        df["load_case"]=df["load_case"].str.replace(r' - for selected objects','')
    except:
        print("Was not able to assign correct load case name to each load case")
    
    df = pd.merge(df,df_load_cases,on=["load_case"])
    return df

def mapFDColumnsToMCColumns(df_from_FD):
    #df: dataframe from FEM-design
    #this function returns a dataframe mapped and scaled according to multicon input files
    
    #note that ID-column from FEM-design is included so splitting into separate excel-files is possible after mapping
    cols_in_MC = ['ID','Load Case Name','LC ', 'NR ', 'ASO [cm2/m]', 'ASOQ [cm2/m]', 'ASU [cm2/m]',
       'ASUQ [cm2/m]', 'mxx [kNm/m]', 'myy [kNm/m]', 'mxy [kNm/m]',
       'vx [kN/m]', 'vy [kN/m]', 'nx [kN/m]', 'ny [kN/m]', 'nxy [kN/m]',
       't [mm]']
    
    corresp_cols_in_FD = ["ID","load_case","No.", "Elem", "x' or r top", "y' or t top", "x' or r bottom",
       "y' or t bottom", "Mx'", "My'", "Mx'y'",
       "Tx'z'", "Ty'z'", "Nx'", "Ny'", "Nx'y'",
       "t1"]
    
    df_mapped = pd.DataFrame(columns=cols_in_MC)
    df_mapped[cols_in_MC]=df_from_FD[corresp_cols_in_FD]

    FD_to_MC_scaling={'ASO [cm2/m]':0.01, 'ASOQ [cm2/m]':0.01, 'ASU [cm2/m]':0.01,
       'ASUQ [cm2/m]':0.01,'t [mm]':1000}

    #scaling units in FEM-design to units in multicon
    for unit in FD_to_MC_scaling:
        df_mapped[unit]=df_mapped[unit]*FD_to_MC_scaling[unit]

    return df_mapped

def proposeElementwiseRebarDiameters(df_mapped,to_excel=False,\
    ouput_xlsx_path="proposed_rebar_diameters.xlsx",ouput_sheet_name="proposed_rebar_diameters"):
    #This function updates df_mapped with proposed rebar diameters
    print("___________________________\n\
            Running rebar proposal")
    test_diameters_list=[12,16,20,25,32]
    test_cc_list=[100,150,200,250]
    print(f"Finding closest match to\ndiameters={test_diameters_list}\nc/c={test_cc_list}\n")

    #Finding columns in df_mapped to propose rebar diameters
    rebar_re = r'AS\w+ \[cm2/m\]' #matching pattern
    rebar_area_names_list = [r for r in df_mapped.columns if re.match(rebar_re,r)] #generating list of ASO [cm2/m] and so on
    
    #Initializing columns in dataframe containing rebar diameters for each element
    diameter_names = ["phi_SO","phi_SOQ","phi_SU","phi_SUQ"]
    id_nr=["ID","NR "]
    df_proposed_rebar_diameters_columns = id_nr+diameter_names
    
    #Initializing dataframe containing rebar diamters
    df_proposed_rebar_diameters=pd.DataFrame(columns=df_proposed_rebar_diameters_columns)
    df_proposed_rebar_diameters[id_nr]=df_mapped[id_nr]

    #Elementwise proposing rebar diameters from df_mapped to df_proposed_rebar_diameters
    df_proposed_rebar_diameters[diameter_names]=\
        df_mapped[rebar_area_names_list].applymap(lambda x: \
            proposeRebarDiameter(x,test_diameters_list=test_diameters_list,test_cc_list=test_cc_list))
    
    #Save proposed rebar diameters to xlsx 
    if to_excel == True:
        df_proposed_rebar_diameters.to_excel(ouput_xlsx_path,sheet_name=ouput_sheet_name,index=False)

    #Columns to merge on
    cols_to_merge_on = df_proposed_rebar_diameters.columns.difference(df_mapped.columns)
    df_mapped=pd.merge(df_mapped,df_proposed_rebar_diameters[cols_to_merge_on],left_index=True,right_index=True,how='outer')
    
    return df_mapped

def splitMappedDataFrameAndSaveToXlsx(df_mapped,sheet_name,keep_unsplit=True,unsplit_xlsx_path="FD_TO_MULTICON_ALL_SHELLS.xlsx"):
    if keep_unsplit==True:
        df_mapped.to_excel(unsplit_xlsx_path,sheet_name=sheet_name,index=False)
    
    df_mapped_grouped = df_mapped.groupby("ID")
    for name,group in df_mapped_grouped:
        df_grouped = group

        df_grouped.drop(columns=["ID"])
        df_grouped.to_excel(name+".xlsx",sheet_name=sheet_name,index=False)

def modifyJsonSettingsByXlsxRowAndRunExcel2Mult(xlsx_path="FD_TO_MULTICON_ALL_SHELLS.xlsx",json_path="settings.json"\
    ,proposeRebars=True):
    #xlsx_path: path to xlsx converted from FEM-design to input for Multicon
    #json_path: path to settings.json
    df = pd.read_excel(xlsx_path)

    for index,row in df.iterrows():
        #values for excel_ouputfile
        xlsx_filename = row["ID"]+".xlsx"
        LC = row["LC "]
        
        #values for multicon inputfile
        phi_SO = row["phi_SO"]
        phi_SOQ = row["phi_SOQ"]
        phi_SU = row["phi_SU"]
        phi_SUQ = row["phi_SUQ"]
        
        docx_filename=row["ID"]

        with open(json_path,"r") as f:
            data = json.load(f)

        #Hard coding changes in dictionary of json-file
        data["excel_outputfile"]["filename"]=xlsx_filename
        data["excel_outputfile"]["LC"]=LC
        
        if proposeRebars == True:
            data["multicon_inputfile"]["phi_SO"] = phi_SO
            data["multicon_inputfile"]["phi_SOQ"] = phi_SOQ
            data["multicon_inputfile"]["phi_SU"] = phi_SU
            data["multicon_inputfile"]["phi_SUQ"] = phi_SUQ

        data["report_outputfile"]["filename"] = docx_filename

        with open(json_path,'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"Running excel2mult with data from {xlsx_filename}")
        try:
            import excel2mult
        except SystemExit:
            continue
            

def runFD_TO_MULTICON(xlsx_path,sheet_name = "XLSX-Export",run_excel2mult=False,\
    n_largest=1,proposeRebars=False,createAllReports=False):
    #xlsx_path: path of xlsx file exported from FEM-design
    #sheet_name: desired sheet_name in excel-file for excel2mult
    #n_largest: the n number of elements with highest sigma 1 from analysis in FEM-design
    
    print(f"Gathering all data into one dataframe where n={n_largest} largest sigma 1 occurs")
    df_load_cases=getLoadCasesDataFrame(xlsx_path)
    df_sigma_1=getShellStressesDataFrame(xlsx_path,n_largest=n_largest)
    df_shell_internal_forces=getShellInternalForcesDataFrame(xlsx_path)
    df_applied_reinforcement=getAppliedReinforcement(xlsx_path)
    df_walls_and_plates = getWallsAndPlatesDataFrame(xlsx_path)
    
    print("Merging dataframes")
    df = mergeDataFrames(df_load_cases,df_sigma_1,df_shell_internal_forces,df_applied_reinforcement,df_walls_and_plates)
    
    print("Mapping dataframes from FEM-design to MULTICON input format")
    df_mapped = mapFDColumnsToMCColumns(df)

    if proposeRebars==True:
        df_mapped=proposeElementwiseRebarDiameters(df_mapped)
    
    print("Grouping dataframes by shell ID and creating seapare .xlsx-files for multicon processing")
    splitMappedDataFrameAndSaveToXlsx(df_mapped,sheet_name = "XLSX-Export")  

    if run_excel2mult==True:
        modifyJsonSettingsByXlsxRowAndRunExcel2Mult(xlsx_path="FD_TO_MULTICON_ALL_SHELLS.xlsx",json_path="settings.json",\
            proposeRebars=proposeRebars)
           
if __name__=="__main__":
    #Reading FEM-design outputs to pandas excel file:
    
    #Going up one dir outside clone of repos
    if "excel2mult.exe" in os.listdir():
        pass
    else:
        os.chdir("..")
        print(f"Accessing output from FEM-design and \
            generating files for multicon in\n{os.getcwd()}")

    #print(getLoadCasesDataFrame(xlsx_path))
    xlsx_path = "FD_EXPORT.xlsx"
    runFD_TO_MULTICON(xlsx_path,sheet_name = "XLSX-Export",run_excel2mult=True,proposeRebars=True)


    #input("Press any key to exit this application")
