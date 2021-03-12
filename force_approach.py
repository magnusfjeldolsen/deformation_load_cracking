import pandas as pd
import openpyxl
import math

### NB, should operate with stresses in coordinate system because pricipal stresses may have different direction at top and bottom! ###

def getLoadCaseName(xlsx_path,sheet):
    #Get name of load case from cell A1 in FEM-design export

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

def getShellForces(xlsx_path):
    #Reading entire workbook by xlsx_path into 
    pd_xlsx=pd.ExcelFile(xlsx_path)
    sigma_top_list=[]
    sigma_bottom_list=[]
    
    for sheet in pd_xlsx.sheet_names:
        df_sheet = pd.ExcelFile.parse(pd_xlsx,sheet,skiprows=1)