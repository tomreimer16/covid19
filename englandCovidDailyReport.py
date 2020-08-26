# import the relevant packages

from requests import get
from json import dumps
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.backends.backend_pdf as backend_pdf
import smtplib
from email import encoders
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from secrets import password
import datetime

# function to get JSON information from API

def get_data(api_params):
    
    ENDPOINT = "https://api.coronavirus.data.gov.uk/v1/data"

    response = get(ENDPOINT, params=api_params, timeout=10)

    if response.status_code >= 400:
        raise RuntimeError(f'Request failed: { response.text }')
        
    return response.json()

def get_df_from_api():
    
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
    apiJson = get_data(api_params)

    # extract the desired data

    df = pd.DataFrame(apiJson["data"])
    df.sort_values(by='date',ascending=True,inplace=True)
    df.reset_index(drop=True, inplace=True)

    return df

def process_df(df):
    # add in new columns

    for i in range(0,df.shape[0]-6):
        sevenDayCases = 0
        sevenDayAdmissions = 0
        sevenDayDeaths = 0
        sevenDayTests = 0

        for j in range(0,6):
            sevenDayCases += df['newCases'][i+j]
            sevenDayAdmissions += df['newAdmissions'][i+j]
            sevenDayDeaths += df['newDeaths'][i+j]
            sevenDayTests += df['P2Tests'][i+j]

        df.loc[df.index[i+6],'sevenDayMACases'] = np.round( (sevenDayCases / 7) ,1)
        df.loc[df.index[i+6],'sevenDayMAAdmissions'] = np.round( (sevenDayAdmissions / 7) ,1)
        df.loc[df.index[i+6],'sevenDayMADeaths'] = np.round( (sevenDayDeaths / 7) ,1)
        df.loc[df.index[i+6],'sevenDayMATests'] = np.round( (sevenDayTests / 7) ,1)

        if i%21 == 0:
            df.loc[df.index[i+6],'threeWeeklyDate'] = df.loc[df.index[i+6],'date']
        else:
            df.loc[df.index[i+6],'threeWeeklyDate'] = ""
        
        if i%7 == 0:
            df.loc[df.index[i+6],'weeklyDate'] = df.loc[df.index[i+6],'date']
        else:
            df.loc[df.index[i+6],'weeklyDate'] = ""


    df["pctAdmissionsPerCase"] = 100.0 * df["sevenDayMAAdmissions"] / df["sevenDayMACases"] 
    df["pctDeathsPerCase"] = 100.0 * df["sevenDayMADeaths"] / df["sevenDayMACases"] 
    df["pctCasesPerTest"] = 100.0 * df["sevenDayMACases"] / df["sevenDayMATests"]

    df = df.replace([np.inf, -np.inf], np.nan)
    df[['threeWeeklyDate']] = df[['threeWeeklyDate']].fillna(value="")
    df[['weeklyDate']] = df[['weeklyDate']].fillna(value="")

    return df

def plotToPdf(df):
    
    minDateInd = df[ df['date']=='2020-07-14'].index.values.astype(int)[0]
    
    outputFile = "englandCovidDailyReport.pdf"

    pdf = backend_pdf.PdfPages(outputFile)

    fig1, ax1 = plt.subplots()
    ax1.plot( 'sevenDayMACases', data=df)
    ax1.plot( 'sevenDayMAAdmissions', data=df)
    ax1.plot( 'sevenDayMADeaths', data=df)
    ax1.legend() 
    plt.xticks(range(0,df.shape[0]) , df['threeWeeklyDate'] , rotation='vertical')
    plt.tight_layout()
    pdf.savefig(fig1)

    fig2, ax2 = plt.subplots()
    ax2.plot( 'pctCasesPerTest', data=df.loc[minDateInd : ])
    ax2.plot( 'pctAdmissionsPerCase', data=df.loc[minDateInd : ])
    ax2.plot( 'pctDeathsPerCase', data=df.loc[minDateInd : ])
    ax2.legend() 
    plt.xticks(range(minDateInd,df.shape[0]) , df[minDateInd : ]['weeklyDate'] , rotation='vertical')
    plt.tight_layout()
    pdf.savefig(fig2)

    fig3, ax3 = plt.subplots()
    ax3.plot( 'sevenDayMATests', data=df.loc[minDateInd : ])
    ax3.legend() 
    plt.xticks(range(minDateInd,df.shape[0]) , df[minDateInd : ]['weeklyDate'] , rotation='vertical')
    plt.tight_layout()
    pdf.savefig(fig3)

    pdf.close()

def email_pdf():  

    fromEmail = 'newsDigest16@gmail.com'
    toEmail = 'tomreimer16@gmail.com'

    msg = MIMEMultipart('alternative')
    msg['Subject'] = "Daily Covid Report -- " + str(datetime.date.today())
    msg["From"] = fromEmail
    msg["To"] = toEmail
    
    html = """\
    <html>
    <body>
        <p>Dear Mr Reimer<br>
        Please find your latest Covid-19 report for England, attached.<br>
        Stay Safe!
        </p>
    </body>
    </html>
    """

    mime = MIMEText(html, 'html')

    msg.attach(mime)

    filename = "englandCovidDailyReport.pdf"

    # Open PDF file in binary mode
    with open(filename, "rb") as attachment:
        # Add file as application/octet-stream
        # Email client can usually download this automatically as attachment
        part = MIMEBase("application", "octet-stream")
        part.set_payload(attachment.read())

    # Encode file in ASCII characters to send by email    
    encoders.encode_base64(part)

    # Add header as key/value pair to attachment part
    part.add_header(
        "Content-Disposition",
        f"attachment; filename= {filename}",
    )

    # Add attachment to message and convert message to string
    msg.attach(part)

    try:
        mail = smtplib.SMTP('smtp.gmail.com', 587)
        mail.ehlo()
        mail.starttls()
        mail.login(fromEmail, password)
        mail.sendmail(fromEmail, toEmail, msg.as_string())
        mail.quit()
        print('Email sent!')
    except Exception as e:
        print('Something went wrong... %s' % e)

def main():
    
    initialDf = get_df_from_api()
    finalDf = process_df(initialDf)
    plotToPdf(finalDf)
    email_pdf()


if __name__ == "__main__":

    main()
