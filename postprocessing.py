"""This script containts functions for converting excel output from FEM-design to crack widths for deformation loads (temperature and shrinkage)

Necessary output from FEM-design:
Load cases
Shells, Stresses, top
Shells, Stresses, bottom

"""
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


def getNLargestSigma1(df_sigma_1,n=1):
    #Returning n largest sigma 1 of each shell
    df_sigma_1["Sigma 1"] = df_sigma_1["Sigma 1"].astype(float)

    df_sigma_1_largest=df_sigma_1.groupby("ID").apply(lambda x: x.nlargest(n,"Sigma 1")).reset_index(drop=True)

    #sorting dataframe by largest to smallest value of Sigma 1
    df_sigma_1_largest=df_sigma_1_largest.sort_values(by=["Sigma 1"])

    return df_sigma_1_largest

# def getShellStressesDataFrame(xlsx_path,n_largest=1):
#     #Reading entire workbook by xlsx_path into 
#     pd_xlsx=pd.ExcelFile(xlsx_path)
#     sigma_1_list=[]
    

#     for sheet in pd_xlsx.sheet_names:
#         df_sheet = pd.ExcelFile.parse(pd_xlsx,sheet,skiprows=1)
        
#         if "Shells, Stresses, top" in sheet:
#             #Getting sheet into a dataframe
#             load_case = getLoadCaseName(xlsx_path,sheet)    
#             df_sheet["load_case"]=load_case

#             sigma_1_list.append(df_sheet)
            
#         elif "Shells, Stresses, bottom" in sheet:
#             load_case = getLoadCaseName(xlsx_path,sheet)
#             df_sheet["load_case"]=load_case
#             sigma_1_list.append(df_sheet)

#     df_sigma_1 = pd.concat(sigma_1_list,ignore_index=True,sort=False)
#     #Removing rows where Sigma 1 is not a number
#     df_sigma_1 = df_sigma_1[pd.to_numeric(df_sigma_1["Sigma 1"], errors = "coerce").notnull()]
#     df_sigma_1=df_sigma_1.rename({"Shell":"ID"},axis=1)

#     #Inserting missing ID-values
#     df_sigma_1=fillMissingStringsInDataFrame(df_sigma_1,"ID")
#     #Filtering out n largest sigma 1 if specified
#     if n_largest is not None:
#         df_sigma_1 = getNLargestSigma1(df_sigma_1,n=n_largest)
#     del df_sheet

#     return df_sigma_1


def getTopBottomShellStressesDataFrame(xlsx_path,n_largest=1):
    #Reading entire workbook by xlsx_path into 
    pd_xlsx=pd.ExcelFile(xlsx_path)
    sigma_top_list=[]
    sigma_bottom_list=[]
    
    for sheet in pd_xlsx.sheet_names:
        df_sheet = pd.ExcelFile.parse(pd_xlsx,sheet,skiprows=1)
        
        if "Shells, Stresses, top" in sheet:
            #Getting sheet into a dataframe
            load_case = getLoadCaseName(xlsx_path,sheet)    
            df_sheet["load_case"]=load_case

            sigma_top_list.append(df_sheet)
            
        elif "Shells, Stresses, bottom" in sheet:
            load_case = getLoadCaseName(xlsx_path,sheet)
            df_sheet["load_case"]=load_case
            sigma_bottom_list.append(df_sheet)

    df_sigma_top = pd.concat(sigma_top_list,ignore_index=True,sort=False)
    df_sigma_top=df_sigma_top.rename(columns={"Sigma 1":"sigma_1_top","Sigma 2":"sigma_2_top","alpha":"alpha_top"})
    
    df_sigma_bottom = pd.concat(sigma_bottom_list,ignore_index=True,sort=False)
    df_sigma_bottom=df_sigma_bottom.rename(columns={"Sigma 1":"sigma_1_bottom","Sigma 2":"sigma_2_bottom","alpha":"alpha_bottom"})

    #merging dataframes
    common_columns_top_bottom = list(set(df_sigma_top.columns).union(set(df_sigma_bottom.columns)))

    # print(common_columns_top_bottom)
    df_sigma = pd.merge(df_sigma_top,df_sigma_bottom,on=["Elem"]).append(common_columns_top_bottom.remove("Elem"))
    
    # #Removing rows where Sigma 1 is not a number
    df_sigma_temp = df_sigma[pd.to_numeric(df_sigma["sigma_1_bottom"], errors = "coerce").notnull()]
    
    # #keeping only necessary columns
    df_sigma=pd.DataFrame(columns=['Shell', 'Elem', 'Node', 'load_case','sigma_1_top', 'sigma_2_top', 'alpha_top','sigma_1_bottom', 'sigma_2_bottom', 'alpha_bottom'])
    df_sigma[['Shell', 'Elem', 'Node', 'load_case','sigma_1_top', 'sigma_2_top', 'alpha_top','sigma_1_bottom', 'sigma_2_bottom', 'alpha_bottom']]=\
        df_sigma_temp[['Shell_x', 'Elem', 'Node_x', 'load_case_x','sigma_1_top', 'sigma_2_top', 'alpha_top','sigma_1_bottom', 'sigma_2_bottom', 'alpha_bottom']]

    return df_sigma

def strainsAtRebars(df_sigma,t,Ec,d_top,v=0.15,d_bottom=None,k_kappa_T=2):
    """Converts linearly elastic stresses to strains
    
    df_sigma: dataframe containing ['Shell', 'Elem', 'Node', 'load_case','sigma_1_top', 'sigma_2_top', 'alpha_top','sigma_1_bottom', 'sigma_2_bottom', 'alpha_bottom']
    t: thickness [mm]
    Ec: E-modulus of concrete [N/mm2], usually 30 000 N/mm2 for B35 when considering cracking
    v: poissons ratio
    k_kappa_T: factor for increasing curvature when cross section cracks. 2.0 is considered conservative after cracks have stabilized

    d_top: d_eff for outer and innter reinforcement layer at top face
    d_bottom: d_eff for outer and innter reinforcement layer at bottom face

    """
    if d_bottom == None:
        d_bottom = d_top
   
    #Curvatures after cracking, including k_kappa_T
    df_sigma['kappa_1_T']=(df_sigma['sigma_1_top']-df_sigma['sigma_1_bottom'])/t*k_kappa_T
    df_sigma['kappa_2_T']=(df_sigma['sigma_2_top']-df_sigma['sigma_2_bottom'])/t*k_kappa_T

    #Average stress in plate:
    df_sigma['sigma_1_mid']=(df_sigma['sigma_1_top']+df_sigma['sigma_1_bottom'])/2
    df_sigma['sigma_2_mid']=(df_sigma['sigma_2_top']+df_sigma['sigma_2_bottom'])/2

    #Linear elastic plate stress at rebar layers
    
    df_sigma['sigma_1_top_at_rebars']=df_sigma['sigma_1_mid']+df_sigma['kappa_1_T']*(d_top-t/2)
    df_sigma['sigma_1_bottom_at_rebars']=df_sigma['sigma_1_mid']+df_sigma['kappa_1_T']*-(d_top-t/2)

    df_sigma['sigma_2_top_at_rebars']=df_sigma['sigma_2_mid']+df_sigma['kappa_2_T']*(d_top-t/2)
    df_sigma['sigma_2_bottom_at_rebars']=df_sigma['sigma_2_mid']+df_sigma['kappa_2_T']*-(d_top-t/2)

    df_epsilon=pd.DataFrame(columns=['epsilon_1_top','epsilon_1_bottom'])
    df_epsilon['epsilon_1_top']=(df_sigma['sigma_1_top_at_rebars']-v*df_sigma['sigma_2_top_at_rebars'])
    df_epsilon['epsilon_1_bottom']=(df_sigma['sigma_1_bottom_at_rebars']-v*df_sigma['sigma_2_bottom_at_rebars'])
    
    return df_epsilon


def Sr_max(df_epsilon,phi,cc,d_top,k1=0.8,k3=3.4,k4=0.425,d_bottom=None):
    """
    This function should be adapted to different reinforcement in different direction. For now, it does not.

    df_epsilon: dataframe containing epsilon_1_top and epsilon_1_bottom
    phi: rebar diameter [mm]
    c: rebar cover

    d_top: d_eff for outer and innter reinforcement layer at top face
    d_bottom: d_eff for outer and innter reinforcement layer at bottom face
    """

    df_epsilon['As_top']=phi**2/4*math.pi*1000/cc
    f_epsilon['As_bottom']=phi**2/4*math.pi*1000/cc
    print(df_epsilon)

    return None

xlsx_path = "FD_STRESSES.xlsx"

# #Getting stresses
df_sigma = getTopBottomShellStressesDataFrame(xlsx_path,n_largest=1)

#Getting stresses at rebars from stresses

t=300
Ec=30000
d_top = t-45-16
df_epsilon = strainsAtRebars(df_sigma,t,Ec,d_top,v=0.15,d_bottom=None,k_kappa_T=2)

phi=16
cc=200

Srmax=Sr_max(df_epsilon,phi,cc,d_top)
print(Srmax)







