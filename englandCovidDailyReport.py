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
        "newCases": "newCasesBySpecimenDate",
        "newAdmissions": "newAdmissions",
        "newDeaths": "newDeaths28DaysByDeathDate",
        "P2Tests": "newPillarTwoTestsByPublishDate",  
        "NewTests": "newTestsByPublishDate"
    }

    api_params = {
        "filters": str.join(";", filters),
        "structure": dumps(structure, separators=(",", ":"))
    }

    # pull in json formatted covid data from the API
    apiJson = get_data(api_params)

    # extract the desired data

    df = pd.DataFrame(apiJson["data"])
    df['date']=pd.to_datetime(df['date'])
    df.sort_values(by='date',ascending=True,inplace=True)
    df.reset_index(drop=True, inplace=True)

    return df

def process_df(df):
    # add in new columns

    for i in range(0,df.shape[0]-6):
        sevenDayCases = 0
        sevenDayAdmissions = 0
        sevenDayDeaths = 0
        sevenDayP2Tests = 0
        sevenDayTests = 0

        for j in range(0,6):
            sevenDayCases += df['newCases'][i+j]
            sevenDayAdmissions += df['newAdmissions'][i+j]
            sevenDayDeaths += df['newDeaths'][i+j]
            sevenDayP2Tests += df['P2Tests'][i+j]
            sevenDayTests += df['NewTests'][i+j]

        df.loc[df.index[i+6],'sevenDayAvgCases'] = np.round( (sevenDayCases / 7) ,1)
        df.loc[df.index[i+6],'sevenDayAvgAdmissions'] = np.round( (sevenDayAdmissions / 7) ,1)
        df.loc[df.index[i+6],'sevenDayAvgDeaths'] = np.round( (sevenDayDeaths / 7) ,1)
        df.loc[df.index[i+6],'sevenDayAvgP2Tests'] = np.round( (sevenDayP2Tests / 7) ,1)
        df.loc[df.index[i+6],'sevenDayAvgTests'] = np.round( (sevenDayTests / 7) ,1)

        if i%21 == 0:
            df.loc[df.index[i+6],'threeWeeklyDate'] = df.loc[df.index[i+6],'date'].strftime('%d %b %Y')
        else:
            df.loc[df.index[i+6],'threeWeeklyDate'] = ""
        
        if i%7 == 0:
            df.loc[df.index[i+6],'weeklyDate'] = df.loc[df.index[i+6],'date'].strftime('%d %b %Y')
        else:
            df.loc[df.index[i+6],'weeklyDate'] = ""


    df["pctAdmissionsPerCase"] = 100.0 * df["sevenDayAvgAdmissions"] / df["sevenDayAvgCases"] 
    df["pctDeathsPerCase"] = 100.0 * df["sevenDayAvgDeaths"] / df["sevenDayAvgCases"] 
    df["pctCasesPerTest"] = 100.0 * df["sevenDayAvgCases"] / df["sevenDayAvgTests"]

    df = df.replace([np.inf, -np.inf], np.nan)
    df[['threeWeeklyDate']] = df[['threeWeeklyDate']].fillna(value="")
    df[['weeklyDate']] = df[['weeklyDate']].fillna(value="")

    return df

def plotToPdf(df):
    
    marchDateInd = df[ df['date']=='2020-03-01'].index.values.astype(int)[0]
    augustDateInd = df[ df['date']=='2020-08-01'].index.values.astype(int)[0]
    outputFile = "englandCovidDailyReport.pdf"

    pdf = backend_pdf.PdfPages(outputFile)


    ### CASES PLOT

    fig1, ax1 = plt.subplots()
    df.plot(y='newCases', kind='bar', ax=ax1)
    df.plot(y='sevenDayAvgCases', kind='line', ax=ax1, color='orange')

    caseFirstMax = df.loc[0 : 100]['sevenDayAvgCases'].max()
    caseFirstMaxPos = df.loc[0 : 100]['sevenDayAvgCases'].idxmax()
    caseFirstMaxDate = pd.to_datetime( df.loc[0 : 100]['date'][caseFirstMaxPos] ).strftime('%d %B')
    ax1.annotate('First Wave Max. Avg:\n' + str(int(caseFirstMax)) + ' on ' + caseFirstMaxDate  , 
                xy=(caseFirstMaxPos+42, caseFirstMax), xytext=(caseFirstMaxPos+42, caseFirstMax+60),
                ha='center' )
    
    caseMin = df.loc[caseFirstMaxPos : ]['sevenDayAvgCases'].min()
    caseMinPos = df.loc[caseFirstMaxPos : ]['sevenDayAvgCases'].idxmin()
    caseMinDate = pd.to_datetime( df.loc[caseFirstMaxPos : ]['date'][caseMinPos] ).strftime('%d %B')
    ax1.annotate('Summer Min. Avg:\n' + str(int(caseMin)) + ' on ' + caseMinDate  , 
                xy=(caseMinPos, caseMin), xytext=(caseMinPos, 1000),
                ha='center' )
    
    ax1.set_xlim(marchDateInd, df.shape[0])

    ax1.legend()
    plt.xticks(range(marchDateInd,df.shape[0]) ,
                df[marchDateInd : ]['threeWeeklyDate'],
                rotation='vertical')
    plt.tight_layout()
    pdf.savefig(fig1)

    ### Admissions / Deaths PLOT

    fig4, ax4 = plt.subplots()
    ax44 = ax4.twinx()

    df.plot(y='sevenDayAvgAdmissions', kind='line', ax=ax4, color='orange', legend=False, rot=90)
    df.plot(y='sevenDayAvgDeaths', kind='line', ax=ax44, color='red', legend=False)

    ax4.set_ylabel('Hospital Admissions')
    ax4.set_ylim(0, 2500)

    ax44.set_ylabel('Deaths')
    ax44.set_ylim(0, 800)
    
    ax4.legend(loc='upper right' , bbox_to_anchor = (0.9, 0.71, 0.09, 0.28) )
    ax44.legend(loc='center right' , bbox_to_anchor = (0.9, 0.71, 0.09, 0.28) )
    plt.xticks(range(marchDateInd,df.shape[0]) , df[marchDateInd : ]['threeWeeklyDate'] , rotation='vertical')
    plt.tight_layout()
    pdf.savefig(fig4)


    ### Percentages PLOT

    fig2, ax2 = plt.subplots()
    ax2.plot( 'pctCasesPerTest', data=df.loc[augustDateInd : ])
    ax2.plot( 'pctAdmissionsPerCase', data=df.loc[augustDateInd : ])
    ax2.plot( 'pctDeathsPerCase', data=df.loc[augustDateInd : ])
    ax2.legend() 

    ax2.set_xlim(augustDateInd, df.shape[0])
    plt.xticks(range(augustDateInd,df.shape[0]) , df[augustDateInd : ]['weeklyDate'] , rotation='vertical')
    ax2.yaxis.set_ticks(np.arange(0, 10, 0.5))
    ax2.set_ylabel("%")

    plt.tight_layout()
    pdf.savefig(fig2)


    ### Tests PLOT

    fig3, ax3 = plt.subplots()
    ax3.plot( 'sevenDayAvgP2Tests', data=df.loc[augustDateInd : ])
    ax3.plot( 'sevenDayAvgTests', data=df.loc[augustDateInd : ])
    ax3.legend() 

    ax3.set_xlim(augustDateInd, df.shape[0])

    plt.xticks(range(augustDateInd,df.shape[0]) , df[augustDateInd : ]['weeklyDate'] , rotation='vertical')
    plt.tight_layout()
    pdf.savefig(fig3)

    ### CLOSE THE PDF

    pdf.close()

def email_pdf(recipients, df):  

    fromEmail = 'newsDigest16@gmail.com'

    msg = MIMEMultipart('alternative')
    msg['Subject'] = "Daily Covid Report"
    msg["From"] = fromEmail
    
    html = """
    <html>
    <body>
        <h2>England Covid-19 Report for %s</h2>
        <br>
        <p>
        <h4>Summary Statistics - 7 day averages (vs last week):</h4>
        Cases: <strong>%s</strong> (%s) <br>
        Admissions: <strong>%s</strong> (%s) <br>
        Deaths: <strong>%s</strong> (%s) <br>
        Tests: <strong>%s</strong> (%s) <br>
        Cases Per Test: <strong>%s</strong>%% (%s%%) <br>
        <br>
        <h4>Notes:</h4>
        <ul>
            <li>Cases are recognised by specimen date, while deaths are recognised by death date</li>
            <li>Admissions are <span style="text-decoration: underline;">confirmed</span> COVID-19 patients admitted to hospital</li>
            <li>Pillar 2 tests are antigen tests conducted by commercial partners of PHE</li>
        </ul>
        <br>
        Stay Safe!
        </p>
    </body>
    </html>
    """% ( datetime.date.today().strftime('%d %B %Y'),
             df["sevenDayAvgCases"].iloc[-1],
             df["sevenDayAvgCases"].iloc[-8],
             df["sevenDayAvgAdmissions"][df["sevenDayAvgAdmissions"].last_valid_index()],
             df["sevenDayAvgAdmissions"][df["sevenDayAvgAdmissions"].last_valid_index()-7],
             df["sevenDayAvgDeaths"][df["sevenDayAvgDeaths"].last_valid_index()],
             df["sevenDayAvgDeaths"][df["sevenDayAvgDeaths"].last_valid_index()-7],
             int(df["sevenDayAvgTests"][df["sevenDayAvgTests"].last_valid_index()]),
             int(df["sevenDayAvgTests"][df["sevenDayAvgTests"].last_valid_index()-7]),
             round( df["pctCasesPerTest"][df["pctCasesPerTest"].last_valid_index()] , 2),
             round( df["pctCasesPerTest"][df["pctCasesPerTest"].last_valid_index()-7] , 2),
             )

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

    for i in recipients:
        toEmail = i
        msg["To"] = toEmail

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

    recipients = ['tomreimer16@gmail.com', 'elliehall@live.com.au', 'danielrthorpe@icloud.com','edwardwilson725@gmail.com']
    email_pdf(recipients, finalDf)

if __name__ == "__main__":

    main()
