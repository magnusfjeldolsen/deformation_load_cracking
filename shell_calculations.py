import numpy as np

E=30000
v=0.15
t=300



def initConcreteCracking():

    E=3*10**10 #N/m**2
    v=0.2 #typical poisons ratio for cracking

    return E,v

def initReinforcementParameters(t,c,phi_xu,cc_xu,\
    phi_yu=None,cc_yu=None,\
        phi_xo=None,cc_xo=None,\
            phi_yo=None,cc_yo=None,\
                outer_u="x",outer_o="x"):
    #This function initializers reinforcement parameters
    
    #t: thickness [mm]
    #c: cover [mm]
    #cc: center distances [mm]

    #phi_xu: armeringsdiamter x-retning, underkant
    #ccx_u: senteravstand armering x-retning, underkant

    

    #defining rebar diameters if missing
    if phi_yu==None:
        phi_yu=phi_xu
    if phi_xo==None:
        phi_xo=phi_xu
    if phi_yo==None:
        phi_yo=phi_xu

    #defining covers
    if outer_u=="x":
        c_xu=c
        c_yu=c+1.25*phi_xu
  
    else:
        c_yu=c
        c_xu=c+1.25*phi_cu

    if outer_o=="x":
        c_xo=c
        c_yo=c+1.25*phi_yo
    else:
        c_yo=c
        c_xo=c+1.25*phi_xo
    
    d_xu = t-c_xu-phi_xu/2
    d_yu = t-c_yu-phi_yu/2
    d_xo = t-c_xo-phi_xo/2
    d_yo = t-c_yo-phi_yo/2

    z_u=t/2-c-1.25*(phi_xu+phi_yu)/2 #avstand fra senter skall til tyngdepunkt armering underkant
    z_o=-(t/2-c-1.25*(phi_xo+phi_yo)/2) #negativt oppover 

    #defining cc distances if missing
    if cc_yu==None:
        cc_yu=cc_xu
    if cc_xo==None:
        cc_xo=cc_xu
    if cc_yo==None:
        cc_yo=cc_xu

    #reinfocement areas [mm2/m]
    As_xu=np.pi*phi_xu**2/4*1000/cc_xu
    As_yu=np.pi*phi_yu**2/4*1000/cc_yu
    As_xo=np.pi*phi_xo**2/4*1000/cc_xo
    As_yo=np.pi*phi_yo**2/4*1000/cc_yo

    rebar_dict = {'x_u':{'phi_xu':phi_xu,'c_xu':c_xu,'cc_xu':cc_xu,'As_xu':As_xu},
    'y_u':{'phi_yu':phi_yu,'c_yu':c_yu,'cc_yu':cc_yu,'As_yu':As_yu},
    'x_o':{'phi_xo':phi_xo,'c_xo':c_xo,'cc_xo':cc_xo,'As_xo':As_xo},
    'y_o':{'phi_yo':phi_yo,'c_yo':c_yo,'cc_yo':cc_yo,'As_yo':As_yo}}

    return rebar_dict

print(initReinforcementParameters(300,35,16,200))

def getEPS_0_N(t,N=np.matrix([[0],[0],[0]]),materialModel=initConcreteCracking,t_unit="mm"):
    #t: thickness [mm]
    #N: column vector of [[Nx, Ny and Nxy]] [kN/m] or [N/mm]
    assert N.shape == (3,1)

    N=N*1000 #scaling to N from kN

    if t_unit=="mm":
        t=t/1000

    E,v = materialModel()
    #constiutive matrix for getting strains in middle plane of shell from axial forces
    C_N=1/(E*t)*np.matrix([[1,-v,0],[-v,1,0],[0,0,2*(1+v)]])
    
    eps_0_N=np.matmul(C_N,N)
    #Convert back to (3,) numpy array
    eps_0_N=np.squeeze(np.asarray(eps_0_N))
    

    return eps_0_N

def getKappa_M(t,M=np.matrix([[0],[0],[0]]),materialModel=initConcreteCracking,t_unit="mm"):

    #t: thickness [m]
    #M: column vector of [[Mx, My and Mxy]] [kNm/m]
    
    assert M.shape == (3,1)

    M=M*1000 #scaling to Nm from kNm

    if t_unit=="mm":
        t=t/1000
   
    E,v = materialModel()
    
    #constiutive matrix for getting curvature of shell from applied moments
    ### wrong?? ###
    C_M=12/(E*t**3)*np.matrix([[1,-v,0],[-v,1,0],[0,0,(1+v)]])

    kappa=np.matmul(C_M,M)
    #Convert back to (3,) numpy array
    kappa=np.squeeze(np.asarray(kappa))

    return kappa

def strainAtZ(eps_0_N,kappa,z,z_unit="mm"):
    
    """
    eps_0_N, eps_0_N[0]: eps_0_x, eps_0_N[1]: eps_0_y, eps_0_N[2]: gamma_0_xy
    kappa, kappa[0]: kappa_x [1/m], kappa[1]: kappa_y [1/m], kappa[2]: kappa_xy [1/m]
    #z [mm]
    """

    if z_unit == "mm":
        z=z/1000


    ### Ask reignard if this is the way it is done
    ### + or minus for combination of kappa and epsilon?
    if eps_0_N[0]-kappa[0]*z>0:
        #when section cracks, the strains jump to bigger values
        #offshore practice in norway, multiply bending contribution by factor of two
        eps_x=eps_0_N[0]-kappa[0]*z*2
    else:
        eps_x=eps_0_N[0]-kappa[0]*z 

    if eps_0_N[1]-kappa[1]*z>0:
        #when section cracks, the strains jump to bigger values
        #offshore practice in norway, multiply bending contribution by factor of two
        eps_y=eps_0_N[1]-kappa[1]*z*2 
    else:
        eps_y=eps_0_N[1]-kappa[1]*z 
    
    gamma_xy=eps_0_N[2]-kappa[2]*z

    eps_z=[eps_x,eps_y,gamma_xy]
    #squeeze to (6,) numpy array
    epz_z=np.squeeze(np.asarray(eps_z))

    return eps_z


def initCrackWidthParameters(t,rebar_dict,kappa,k1=0.8,k3=3.4,k4=0.425,t_unit = "mm"):
    
    #Checking if bending is present, setting k2=0,5 if bending, 1 if not
    if kappa[0]!=0 or kappa[1]!=0:
        k2=0.5
    else:
        k2 = 1.0
    
    if t_unit =="mm":
        t=t/1000
        b=1

    return None

if __name__=="__main__":

    #Axial force - testing
    Nx=0
    Ny=0
    Nxy=0
    N=np.matrix([[Nx],[Ny],[Nxy]])

    #Moments - testing
    Mx=0.339
    My=0.339
    Mxy=3.168
    M=np.matrix([[Mx],[My],[Mxy]])

    t=200
    
    eps_0_N=getEPS_0_N(t,N=N)
    print("eps_0_N")
    print(eps_0_N)
    print(eps_0_N[0])
    print(eps_0_N.shape)

    kappa=getKappa_M(t,M=M)
    print(f"kappa:\n{kappa}")
    print(kappa[1])
    print(kappa.shape)
    
    strains=strainAtZ(eps_0_N,kappa,t/2)
    print(f"strains: {strains}")
    
