
import openai
import requests
from bs4 import BeautifulSoup
import urllib.parse
import csv
import json
import time
from dotenv import load_dotenv
import os

load_dotenv()

# Set your OpenAI API key
openai.api_key=os.getenv('OPENAI_API_KEY')


# Function to extract text from a URL
def extract_text_from_url(url):
    try:
        page = requests.get(urllib.parse.unquote(url))
        if page.status_code == 200:
            soup = BeautifulSoup(page.text, 'html.parser')

            extract_h1 = soup.find('h1', class_='title')
            extract_div = soup.find('div', class_='lessme')

            if extract_h1 is not None and extract_div is not None:
                h1_text = extract_h1.text.strip()
                div_text = extract_div.text.strip()
                extracted_text = h1_text + '. ' + div_text
                return extracted_text
            else:
                return "Elements not found on the page."
        else:
            return "Failed to retrieve the web page."
    except requests.exceptions.RequestException as e:
        return f"An error occurred: {e}"

# Read the URLs from the file
with open("sampled_url.txt", "r") as f:
    urls = f.readlines()

# Global variables to track the last request time and total tokens used
last_request_time = 0
total_tokens_used = 0

# Function to analyze text using ChatGPT API with a custom template
def analyze_text_with_gpt(text):
    global last_request_time
    global total_tokens_used
    
    retry_count = 3  # Number of retries in case of rate limit errors
    wait_duration = 10  # Duration (in seconds) to wait before retrying
    max_tokens_per_request = 3000  # Max tokens for each request
    
    for _ in range(retry_count):
        try:
            # Calculate the time since the last request
            elapsed_time = time.time() - last_request_time
            
            # If less than 1 second has passed since the last request, wait
            if elapsed_time < 1:
                time.sleep(1 - elapsed_time)
            
            # Check the token limit
            if total_tokens_used + max_tokens_per_request > 150000:
                # If the token limit would be exceeded, wait until the next minute
                time.sleep(60 - (time.time() % 60))
                total_tokens_used = 0  # Reset the token count for the new minute

            # Rest of the OpenAI API call logic
            custom_template = """
            "Listeners": Please enter the full name of the listener or listeners without any additional text. It must be a persons' name. If the name is in Pronoun form (such as "I", "He", "She"), is used, use the listeners name.
            "Listening to": Please specify only the title or name of what is being listening to, without any extra details.
            "Performed by": Mention who performed or delivered the content being listened to.
            "Date/Time": Extract all date and time in whatever format they appear in the provided text. then, you must convert the date and time to UTC in the format 'YYYY-MM-DDTHH:MM:SSZ'. If Month, Day, time (Hour, Minutes, Seconds) are missing in the text, use '00' for them".
            "Medium": Choose one from - "Live", "Playback", "Broadcast", or "Others". Choose Live, if the context relates to live music performances where the listener is present at the venues or events such as: Concerts, Theatres, Parks, Clubs, Bars, Street Performances, House Concerts, Stadiums, Coffee Shops, Churches, Cathedrals, Open Mics, Radio Shows, or TV Shows. Choose Playback, if the text relates to any of the following and is not associated with live music performances: Album, MP3, Vinyl, CD, Tapes, 8-Track Tapes, Digital Downloads, FLAC, Radio (for prerecorded music), Music Videos, Podcasts (music-focused, on-demand), Satellite Radio, WAV, Streaming (e.g., Spotify, Apple Music), Bluetooth Speakers, or Wireless Headphones. Choose Broadcast, if the text relates to any of the following methods or platforms for disseminating music, regardless of whether the music is live or pre-recorded such as: Radio (AM, FM, Shortwave), Television, Music TV channels, Talent shows, Award ceremonies, Internet Radio, Satellite Radio, Podcasts (for music distribution), Webcasts, Live Streaming Platforms, Public Address Systems, or DAB (Digital Audio Broadcasting). Choose Others, If the text does not fit the above categories.
            "Listening Environment": Select all the listening environment that applied to the excerpt from the following - "Indoors", "In the company of others", "In Public", "In Private", "Solitary", "Outdoors", "Domestic", "Accompanied", or "Others". Select Indoors, if the environment is Home, office, commercial places (e.g., malls, restaurants), public facilities (e.g., libraries, train stations). Select Outdoors, if the environment is Parks, streets, beaches, wilderness (e.g., forests, mountains). Select Solitary, if the listener was Alone in the environment, without any other human presence. Select In the Company of Others, if the listener was Listening with family, friends, colleagues, or strangers. Select "In Private", if the Listening happend in private places, like personal homes or offices. Select In Public", if the environment is an Area with multiple people and reduced privacy. Select Domestic, if the listener Listened within household settings, which might include living rooms, bedrooms, or kitchens. Select "Accompanied", if the listener was Listening with one or more individuals, regardless of the relationship or setting. Select Others", if the listening environment did not fit any of the above categories.
            "Location": Provide the city and country.
            """
            prompt_message = f"Act as a knowledge engineer with over 25 years of experience in information extraction, analyze the passage below and determine any encounters depicted within it. Please provide a concise answer. Respond using a JSON structure with the following seven keys as per the custom template:\n\n{text}"

            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": custom_template},
                    {"role": "user", "content": prompt_message}
                ],
                temperature=0,
                max_tokens=max_tokens_per_request
            )
            
            # Update the last request time and total tokens used
            last_request_time = time.time()
            total_tokens_used += max_tokens_per_request
            
            # Get the generated answer from the response
            answer = response.choices[0].message.content.strip()
            return answer
        
        except openai.error.OpenAIError as e:
            # Check if the error is a rate limit error
            if "Rate limit reached" in str(e):
                time.sleep(wait_duration)
                continue
            return f"An error occurred: {e}"

    return "Failed to analyze the text after multiple retries."

# Process each URL, extract text, analyze it and get Gold Standard details
def extract_gold_standard(url):
    data = {}
    
    page = requests.get(urllib.parse.unquote(url))
    if page.status_code == 200:
        soup = BeautifulSoup(page.text, 'html.parser')

        # Listeners
        listener_element = soup.find('span', property="http://www.w3.org/2000/01/rdf-schema#label")
        data['Listener'] = listener_element.text if listener_element else "Not Available"

        # Listening to
        #data['Listening to'] = soup.find('table', class_='setlist').td.a.text

        table_element = soup.find('table', class_='setlist')
        if table_element:
            data['Listening to'] = table_element.td.a.text if table_element.td and table_element.td.a else "Not Available"
        else:
            data['Listening to'] = "Not Available"

        performed_by_elements = soup.find_all(property="http://purl.org/ontology/mo/performer")
        texts = [element.text for element in performed_by_elements]
        data['Performed by'] = ', '.join(texts) if texts else "Not Available"


        # Experience Information
        date_time_element = soup.find(property="http://purl.org/NET/c4dm/event.owl#time")
        if date_time_element is not None and date_time_element.span is not None:
            data['Date/Time'] = date_time_element.span.text
        else:
            data['Date/Time'] = "Not Available"  # or any other default value

        medium_element = soup.find(property="http://led.kmi.open.ac.uk/term/has_medium")
        data['Medium'] = medium_element.text if medium_element else "Not Available"

        listening_environment_elements = soup.find_all(property="http://led.kmi.open.ac.uk/term/has_environment")
        texts = [element.text for element in listening_environment_elements]
        data['Listening Environment'] = ', '.join(texts) if texts else "Not Available"


        # Location
        location_element = soup.find('span', style="font-size:1.2em")
        data['Location'] = location_element.a.text if location_element and location_element.a else "Not Available"

    return data


csv_filename = 'analysis_resultsGPT4w.csv'
write_headers = not os.path.exists(csv_filename)
    
# Process each URL
for url in urls:
    url = url.strip()
    extracted_text = extract_text_from_url(url)
    if extracted_text != "Elements not found on the page.":
        # Analyze the text using ChatGPT with the custom template
        analysis_result = analyze_text_with_gpt(extracted_text)
        
        # Extract Gold Standard details
        gold_standard_details = extract_gold_standard(url)
        
        # Create a JSON structure for the analysis result and Gold Standard details
        analysis_data = {
            "URL": url,
            "Extracted Text": extracted_text,  # Add the extracted text
            "Analysis Result": analysis_result,
            "Gold Standard": json.dumps(gold_standard_details, indent=4)  # Storing as a JSON string
        }
        #all_data.append(analysis_data)

        # Calculate Accuracy, Precision, and Recall
        analysis_result_set = set(analysis_result.split())
        gold_standard_set = set(gold_standard_details.values())
        
        # Calculate True Positives, False Positives, and False Negatives
        true_positives = len(analysis_result_set.intersection(gold_standard_set))
        false_positives = len(analysis_result_set - gold_standard_set)
        false_negatives = len(gold_standard_set - analysis_result_set)
        
        # Calculate Accuracy, Precision, and Recall
        accuracy = true_positives / (true_positives + false_positives + false_negatives) if true_positives + false_positives + false_negatives > 0 else 0
        precision = true_positives / (true_positives + false_positives) if true_positives + false_positives > 0 else 0
        recall = true_positives / (true_positives + false_negatives) if true_positives + false_negatives > 0 else 0
        
        analysis_data["Accuracy"] = accuracy
        analysis_data["Precision"] = precision
        analysis_data["Recall"] = recall
        
        #all_data.append(analysis_data)

    # Save the data in a CSV file immediately
    with open(csv_filename, 'a', newline='') as csvfile:
        fieldnames = ["URL", "Extracted Text", "Analysis Result", "Gold Standard",  "Accuracy", "Precision", "Recall"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        # If headers need to be written (i.e., file didn't exist before), write them
        if write_headers:
            writer.writeheader()
            write_headers = False  # Headers are written, so update the flag

        writer.writerow(analysis_data)


print(f"Analysis results saved in {csv_filename}")
