# import the relevant packages

from requests import get
from json import dumps
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.backends.backend_pdf as backend_pdf

# function to get JSON information from API

def get_data(api_params):
    
    ENDPOINT = "https://api.coronavirus.data.gov.uk/v1/data"

    response = get(ENDPOINT, params=api_params, timeout=10)

    if response.status_code >= 400:
        raise RuntimeError(f'Request failed: { response.text }')
        
    return response.json()

if __name__ == "__main__":
    
    # define out parameters for the API call

    AREA_TYPE = "nation"
    AREA_NAME = "england"

    filters = [
        f"areaType={ AREA_TYPE }",
        f"areaName={ AREA_NAME }"
    ]

    structure = {
        "date": "date",
        "name": "areaName",
        "newCases": "newCasesByPublishDate",
        "newAdmissions": "newAdmissions",
        "newDeaths": "newDeaths28DaysByDeathDate",
        "P2Tests": "newPillarTwoTestsByPublishDate"  
    }


    api_params = {
        "filters": str.join(";", filters),
        "structure": dumps(structure, separators=(",", ":"))
    }

    # pull in json formatted covid data from the API
    englandJson = get_data(api_params)

    # extract the desired data

    englandPd = pd.DataFrame(englandJson["data"])
    englandPd.sort_values(by='date',ascending=True,inplace=True)
    englandPd.reset_index(drop=True, inplace=True)

    # add in new columns

    for i in range(0,englandPd.shape[0]-6):
        sevenDayCases = 0
        sevenDayAdmissions = 0
        sevenDayDeaths = 0
        sevenDayTests = 0

        for j in range(0,6):
            sevenDayCases += englandPd['newCases'][i+j]
            sevenDayAdmissions += englandPd['newAdmissions'][i+j]
            sevenDayDeaths += englandPd['newDeaths'][i+j]
            sevenDayTests += englandPd['P2Tests'][i+j]

        englandPd.loc[englandPd.index[i+6],'sevenDayMACases'] = np.round( (sevenDayCases / 7) ,1)
        englandPd.loc[englandPd.index[i+6],'sevenDayMAAdmissions'] = np.round( (sevenDayAdmissions / 7) ,1)
        englandPd.loc[englandPd.index[i+6],'sevenDayMADeaths'] = np.round( (sevenDayDeaths / 7) ,1)
        englandPd.loc[englandPd.index[i+6],'sevenDayMATests'] = np.round( (sevenDayTests / 7) ,1)

        if i%21 == 0:
            englandPd.loc[englandPd.index[i+6],'threeWeeklyDate'] = englandPd.loc[englandPd.index[i+6],'date']
        else:
            englandPd.loc[englandPd.index[i+6],'threeWeeklyDate'] = ""
        
        if i%7 == 0:
            englandPd.loc[englandPd.index[i+6],'weeklyDate'] = englandPd.loc[englandPd.index[i+6],'date']
        else:
            englandPd.loc[englandPd.index[i+6],'weeklyDate'] = ""


    englandPd["pctAdmissionsPerCase"] = 100.0 * englandPd["sevenDayMAAdmissions"] / englandPd["sevenDayMACases"] 
    englandPd["pctDeathsPerCase"] = 100.0 * englandPd["sevenDayMADeaths"] / englandPd["sevenDayMACases"] 
    englandPd["pctCasesPerTest"] = 100.0 * englandPd["sevenDayMACases"] / englandPd["sevenDayMATests"]

    englandPd = englandPd.replace([np.inf, -np.inf], np.nan)
    englandPd[['threeWeeklyDate']] = englandPd[['threeWeeklyDate']].fillna(value="")
    englandPd[['weeklyDate']] = englandPd[['weeklyDate']].fillna(value="")

    minDateInd = englandPd[ englandPd['date']=='2020-07-14'].index.values.astype(int)[0]
    

    outputFile = "englandCovidDailyReport.pdf"
    pdf = backend_pdf.PdfPages(outputFile)

    fig1, ax1 = plt.subplots()
    ax1.plot( 'sevenDayMACases', data=englandPd)
    ax1.plot( 'sevenDayMAAdmissions', data=englandPd)
    ax1.plot( 'sevenDayMADeaths', data=englandPd)
    ax1.legend() 
    plt.xticks(range(0,englandPd.shape[0]) , englandPd['threeWeeklyDate'] , rotation='vertical')
    plt.tight_layout()
    pdf.savefig(fig1)

    fig2, ax2 = plt.subplots()
    ax2.plot( 'pctCasesPerTest', data=englandPd.loc[minDateInd : ])
    ax2.plot( 'pctAdmissionsPerCase', data=englandPd.loc[minDateInd : ])
    ax2.plot( 'pctDeathsPerCase', data=englandPd.loc[minDateInd : ])
    ax2.legend() 
    plt.xticks(range(minDateInd,englandPd.shape[0]) , englandPd[minDateInd : ]['weeklyDate'] , rotation='vertical')
    plt.tight_layout()
    pdf.savefig(fig2)

    fig3, ax3 = plt.subplots()
    ax3.plot( 'sevenDayMATests', data=englandPd.loc[minDateInd : ])
    ax3.legend() 
    plt.xticks(range(minDateInd,englandPd.shape[0]) , englandPd[minDateInd : ]['weeklyDate'] , rotation='vertical')
    plt.tight_layout()
    pdf.savefig(fig3)

    #plt.show()
    pdf.close()
