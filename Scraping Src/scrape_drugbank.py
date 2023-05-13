from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException
from selenium.common.exceptions import StaleElementReferenceException
from selenium.webdriver.chrome.options import Options

import pandas as pd
import time

# Set up Chrome options
chrome_options = Options()
chrome_options.add_argument('--headless')

# Launch Chrome in headless mode
driver = webdriver.Chrome(options=chrome_options)

scrape_label = 0
studies_df = pd.read_csv("parkinsons_studies.csv",
                         names=["Study ID", "Study Description", "Label"]).dropna()

studies_df = studies_df[studies_df["Label"] == scrape_label]

set_drugs = set()
drugs_df = pd.DataFrame(columns=["Drug ID", "Drug Name", "Study Phase",
                                 "Status", "Label"])

count = 0

for i, row in studies_df.iterrows():

    print(count, "/", len(studies_df))
    count += 1

    if count < 1000:
        continue
    if count > 3000:
        break

    try:
        study_id = row["Study ID"]
        # print(study_id)
        study_label = row["Label"]

        driver.get('https://www.cdek.liu.edu/trial/' + study_id)

        list_items = driver.find_elements(By.CLASS_NAME, "label")
        # phase = list_items[0].text
        # sponsor = list_items[1].text
        # study_type = list_items[2].text
        # status = list_items[3].text
        phase = driver.find_elements(
            By.XPATH, "//li[@class='list-group-item']")[0].text[6:]

        drugs_tab = driver.find_elements(
            By.XPATH, "//li[@class='list-group-item']")[5]

        drug_anchors = drugs_tab.find_elements(
            By.XPATH, ".//a[@target='_blank']")
    except:
        continue

    for drug_anchor in drug_anchors:
        try:
            drug_anchor.click()

            driver.switch_to.window(driver.window_handles[1])
            driver.implicitly_wait(0)
            drugbank_anchor = driver.find_element(
                By.XPATH, "//*[contains(text(), 'DrugBank')]")
            drugbank_anchor.click()
            driver.switch_to.window(driver.window_handles[2])
            driver.implicitly_wait(0)

            first_dl = driver.find_element(By.TAG_NAME, "dl")
            dts_list = [x.text for x in first_dl.find_elements(
                By.TAG_NAME, "dt")]

            dds_list = first_dl.find_elements(By.TAG_NAME, "dd")

            drug_name = driver.find_element(By.TAG_NAME, "h1").text

            try:
                drugbank_id = dds_list[dts_list.index(
                    'DrugBank Accession Number')].text
            except:
                drugbank_id = ""
            try:
                drug_approval = dds_list[dts_list.index(
                    'Groups')].text.replace(",", ";")
            except:
                drug_approval = ""

            if not (drugbank_id in set_drugs):
                set_drugs.add(drugbank_id)
                drugs_df.loc[len(drugs_df)] = [drugbank_id, drug_name, phase,
                                               drug_approval, int(study_label)]
                print(drugbank_id, drug_name, phase,
                      drug_approval, int(study_label))
            driver.close()
        except:
            pass

        try:
            for handle in driver.window_handles[1:]:
                driver.switch_to.window(handle)
                driver.close()
        except:
            pass
        # Switch back to the original tab
        driver.switch_to.window(driver.window_handles[0])
        driver.implicitly_wait(1)

# driver.implicitly_wait(3)

drugs_df.to_csv("./scraped_drugs_" + str(scrape_label) + ".csv")
driver.quit()


# import pandas as pd
# import re

# full_df = pd.concat([pd.read_csv("scraped_drugs_0.csv"), pd.read_csv(
#     "./scraping_data/scraped_drugs_0.csv"), pd.read_csv("./scraping_data/scraped_drugs_1.csv")]).reset_index().drop(columns=["Unnamed: 0", "index"])

# full_df["Phase Num"] = full_df["Study Phase"].apply(
#     lambda x: re.sub("[^\d]", "", str(x)) if len(re.sub("[^\d]", "", str(x))) <= 1 else re.sub("[^\d]", "", str(x))[-1])

# final_df = full_df.sort_values(["Phase Num", "Drug Name"]
#                                ).dropna().drop(columns=["Phase Num"])

# final_df.to_csv("final_scraped_df.csv")
