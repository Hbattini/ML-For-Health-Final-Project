from langchain.llms import OpenAI
import os

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options

import pandas as pd
import numpy as np
import time

# Set up Chrome options
chrome_options = Options()
chrome_options.add_argument('--headless')

# Launch Chrome in headless mode
driver = webdriver.Chrome(options=chrome_options)

scrape_ibkh = False
disease_name = "parkinson's disease 2"
ibkh_filename = "iBKH/IBKH_" + disease_name.replace(" ", "_") + ".csv"
iBKH_df = None

# Scrape IBKH
print("## Started Scraping iBKH ## \n")
if scrape_ibkh:
    driver.get("http://54.92.218.239:8000/analysis?browse_type=lp")
    driver.find_element(
        By.XPATH, "//input[@placeholder='Please Select Entity Type']").click()
    driver.find_element(
        By.XPATH, "//dd[@lay-value='Disease']").click()
    driver.find_element(
        By.XPATH, "//input[@placeholder='Top N']").click()

    top_n_value = 300
    driver.find_elements(
        By.XPATH, "//dd[@lay-value=" + str(top_n_value) + "]")[0].click()
    driver.find_element(By.ID, "entity_name_lp").send_keys(
        disease_name + Keys.ENTER)

    driver.implicitly_wait(20)

    drugs_table = driver.find_elements(
        By.XPATH, "//table[@lay-filter='index_table']")[0]
    table_titles = np.array([
        th.get_attribute("textContent") for th in drugs_table.find_elements(By.XPATH, "//thead/tr/th/div")])

    table_titles = table_titles[table_titles != ""][:7]

    table_values = np.array([
        td.get_attribute("textContent") for td in drugs_table.find_elements(By.XPATH, "//tr/td")])

    table_values = table_values[table_values !=
                                ""][: (top_n_value * len(table_titles))]

    print(table_values)
    iBKH_df = pd.DataFrame(
        data=table_values.reshape(-1, len(table_titles)), columns=table_titles)

    iBKH_df["Primary_ID"] = iBKH_df["Primary_ID"].apply(lambda x: x[9:-1])
    iBKH_df.to_csv(ibkh_filename, index=None)

else:
    iBKH_df = pd.read_csv(ibkh_filename)

print(iBKH_df)
print("## Finished Scraping iBKH ## \n")


dname_to_dbid_dynamic_dict = {}


def scrape_actual_dbid(drug_name):
    if drug_name in dname_to_dbid_dynamic_dict:
        return dname_to_dbid_dynamic_dict[drug_name]
    else:
        driver.get('https://go.drugbank.com/')
        driver.find_element(By.ID, "query").send_keys(
            str(drug_name) + Keys.ENTER)
        actual_dbid = driver.current_url.split("/")[-1]
        actual_dbid = actual_dbid if actual_dbid[0:2] == "DB" else None

        dname_to_dbid_dynamic_dict[drug_name] = actual_dbid
        return actual_dbid


# Final analysis df
analysis_df = pd.DataFrame(columns=["Model", "Temperature", "Max Tokens",
                                    "Aware of Drug's Existance",
                                    "Drug Detection Error Rate",
                                    "Correct DBID Rate", "Correct Drugs"])

# OpenAI Setup
os.environ["OPENAI_API_KEY"] = "<INSERT-YOUR-KEY>"
questions_file = "questions.txt"

model_list = ["gpt-3.5-turbo", "gpt-4"]
temperature_list = [0, 0.25, 0.5, 0.75, 1]

# model_list = ["gpt-3.5-turbo"]
# temperature_list = [0.2, 0.9]

for model_name in model_list:
    for temperature in temperature_list:
        print("## Start Scraping " + model_name +
              " with temp: " + str(temperature) + " ## \n")

        max_tokens = 512
        llm = OpenAI(model_name=model_name,
                     temperature=temperature, max_tokens=max_tokens, presence_penalty=0.3,
                     n=2)

        is_aware = "Yes"
        detection_error_rate, dbid_correct_rate, gpt_df = None, None, None

        questions_idx = 0
        with open("./" + questions_file) as file:
            while line := file.readline():
                question = line.rstrip()
                expected_output = "yes"
                answer = llm(question).replace("\n", "")

                if questions_idx == 0 and (answer.lower() != expected_output):
                    print("Answer:\t", answer,
                          " does not match expected output:\t", expected_output)
                    is_aware = "No"
                    break

                elif questions_idx == 1:
                    try:
                        file_name = "llm-outputs/" + model_name + \
                            "-temp" + str(temperature) + ".csv"
                        f = open(file_name, "w")

                        # return if answer seems to not contain useful data
                        if answer.find('DB') == -1:
                            break

                        answer = ("LLM Predicted DrugBank ID,Drug NameDB" +
                                  "DB".join(answer.split("DB")[-20:])).replace(
                            "DB", "\nDB")

                        f.write(answer)
                        f.close()

                        gpt_df = pd.read_csv(file_name)

                        # scrape real DBID
                        gpt_df["Actual DrugBank ID"] = gpt_df["Drug Name"].apply(
                            scrape_actual_dbid)

                        gpt_df[["Actual DrugBank ID", "LLM Predicted DrugBank ID",
                                "Drug Name"]].to_csv(file_name, index=None)
                    except:
                        break

                questions_idx += 1

            print(gpt_df)
            print("## Finished Scraping " + model_name +
                  " with temp: " + str(temperature) + " ## \n")

            # final analysis
            print("## Starting Final Analysis" + model_name +
                  " with temp: " + str(temperature) + " ## \n")

            try:
                detection_error_rate = str(gpt_df["Actual DrugBank ID"].isna(
                ).sum() / float(len(gpt_df["Actual DrugBank ID"])) * 100) + " %"

            except:
                detection_error_rate = None
            try:
                dbid_correct_rate = 0
                for act_dbid, pred_dbid in zip(gpt_df["Actual DrugBank ID"],  gpt_df["LLM Predicted DrugBank ID"]):
                    if str(act_dbid).lower().replace(" ", "") == str(pred_dbid).lower().replace(" ", ""):
                        dbid_correct_rate += 1 / \
                            float(len(gpt_df["Actual DrugBank ID"]))

                dbid_correct_rate = str(dbid_correct_rate * 100) + " %"

            except:
                dbid_correct_rate = None

            try:
                set_ibkh_drugs = set(iBKH_df["Primary_ID"])
                count_correct_drugs = 0
                for dbid in gpt_df["Actual DrugBank ID"]:
                    if dbid in set_ibkh_drugs:
                        count_correct_drugs += 1
                        print(iBKH_df[iBKH_df["Primary_ID"] == dbid])

                correc_drugs_rate = str(
                    count_correct_drugs / float(len(gpt_df["Actual DrugBank ID"])) * 100) + " %"
            except:
                correc_drugs_rate = None
            analysis_df.loc[len(analysis_df)] = [model_name, temperature, max_tokens,
                                                 is_aware, detection_error_rate, dbid_correct_rate, correc_drugs_rate]

            print(analysis_df)
            print("## Finished Final Analysis " + model_name +
                  " with temp: " + str(temperature) + " ## \n")

analysis_df.to_csv("./final_analysis/final_table.csv", index=None)
