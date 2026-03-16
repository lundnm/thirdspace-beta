### User Data Cleaning Script ##
import pandas as pd
import regex as re
from thefuzz import process, fuzz

MASTER_TEAMS = pd.read_csv("../data/master_teams.csv")
NBA_TEAMS = MASTER_TEAMS[MASTER_TEAMS['League'] == 'NBA']['Team Name'].tolist()
CBB_TEAMS = MASTER_TEAMS[MASTER_TEAMS['League'].str.contains("CBB")]['Team Name'].unique().tolist()

POSSIBLE_FEATURES = [
    "Traditional Sports Bar Environment (Multiple screens/high energy)",
    "Quality Beer Selection",
    "Signature Cocktails & Spirits",
    "High-Quality Food Menu (Beyond standard pub fare)",
    "Family-Friendly Atmosphere"
]

CORRECTION_MAP = {
    "um": "University of Michigan",
    "michigan": "University of Michigan",
    "wolverines": "University of Michigan",
    "msu": "Michigan State University",
    "unc": "University of North Carolina",
    "uconn": "University of Connecticut",
    "ucla": "University of California Los Angeles",
    "lsu": "Louisiana State University",
    "lakers": "Los Angeles Lakers",
    "knicks": "New York Knicks",
    
    # These catch the schools if their commas were stripped during the input split
    "university of california los angeles": "University of California Los Angeles",
    "california state university fullerton": "California State University, Fullerton"
}

def convert_venuesFeatures_to_vectors(venueFeatures, possible_features):
    """Convert the venue features string into a vector of binary features.

    Possible features include:
    - Traditional Sports Bar Environment (Multiple screens/high energy)
    - Quality Beer Selection
    - Signature Cocktails & Spirits
    - High-Quality Food Menu (Beyond standard pub fare)
    -Family-Friendly Atmosphere

    If a user submits a new feature, then print message to consider adding it to the possible features list.


    """
    # Initialize the vector with zeros
    feature_vector = [0] * len(possible_features)

    # Split the input string into individual features
    features = re.split(r',\s*', venueFeatures)

    # Check each feature against the possible features and set the corresponding index to 1
    for feature in features:
        feature = feature.strip()  # Remove leading/trailing whitespace
        if feature in possible_features:
            index = possible_features.index(feature)
            feature_vector[index] = 1
        if feature not in possible_features:
            print(f"Feature '{feature}' not recognized. Consider adding it to the possible features list.")

    return feature_vector

def clean_email(email):
    # Convert to lowercase
    email = email.lower()
    
    # Remove leading and trailing whitespace
    email = email.strip()
    
    # Remove any characters that are not allowed in an email address
    email = re.sub(r'[^\w\.\-@]+', '', email)
    
    return email

def clean_basketball_survey_data(df):
    """
    Cleans team names, handles numbered lists, and returns a semicolon-separated string.
    """
    mbb_col = "MCBB"
    wbb_col = "WCBB"
    nba_col = "NBA"
    
    cols_to_clean = [mbb_col, wbb_col, nba_col]
    
    def process_response(response):
        if pd.isna(response) or str(response).strip() == "":
            return None
        
        response = str(response)
        
        # 1. Strip out numbered lists (e.g., "1. ", "2)", "3 - ")
        response = re.sub(r'\b\d+[\.\)\-]\s*', '', response)
        
        # 2. Split the teams based on how the user formatted their input
        if '\n' in response:
            # If they used newlines, split by newlines (protects all commas naturally)
            raw_teams = [team.strip() for team in response.split('\n')]
        else:
            # If they typed on one line, temporarily remove UC/CSU commas so we can split safely
            response = re.sub(r'(?i)(California|University),\s+(Los Angeles|Fullerton|Irvine|Davis|Berkeley|San Diego|Santa Barbara|Santa Cruz|Riverside)', r'\1 \2', response)
            
            # Standardize delimiters to commas, then split
            response = re.sub(r'(?i)\s+and\s+|\s*&\s*|\s*/\s*|\s*;\s*', ',', response)
            raw_teams = [team.strip() for team in response.split(',')]
        
        cleaned_teams = []
        for team in raw_teams:
            if not team: 
                continue
            
            # 3. Apply corrections or standardize casing
            lower_team = team.lower()
            if lower_team in CORRECTION_MAP:
                cleaned_teams.append(CORRECTION_MAP[lower_team])
            else:
                cleaned_teams.append(team.title())
                
        # 4. Return as a SAFE, semicolon-separated string!
        return "; ".join(cleaned_teams)

    for col in cols_to_clean:
        if col in df.columns:
            df[col] = df[col].apply(process_response)
            
    return df

def apply_fuzzy_matching(df, master_team_lists, threshold=85):
    """
    Applies fuzzy matching to correct misspelled team names.
    
    Parameters:
    - df: The pandas DataFrame containing the cleaned columns.
    - master_team_lists: A dictionary mapping column names to a list of valid teams.
    - threshold: The minimum similarity score (0-100) required to accept a match.
    """
    
    def fuzzy_match_list(teams_string, valid_teams):
        # Handle empty/NaN values
        if pd.isna(teams_string) or str(teams_string).strip() == "":
            return None
            
        # Split the semicolon-separated string back into a list
        teams = [t.strip() for t in str(teams_string).split(";")]
        
        matched_teams = []
        for team in teams:
            # Skip if the team name is already perfectly in the master list
            if team in valid_teams:
                matched_teams.append(team)
                continue
                
            # Use thefuzz to find the closest match
            # extractOne returns a tuple: (Best Match String, Score, Index)
            best_match, score = process.extractOne(
                team, 
                valid_teams, 
                scorer=fuzz.token_sort_ratio # Good for handling out-of-order words
            )
            
            # If the score meets our confidence threshold, use the corrected name
            if score >= threshold:
                matched_teams.append(best_match)
            else:
                # If the score is too low, keep the original (or flag it for manual review)
                matched_teams.append(team)
                print(f"Team '{team}' did not match any valid team with sufficient confidence. Consider reviewing this entry.")
                
        return "; ".join(matched_teams)

    # Apply to each column that has a corresponding master list
    for col, valid_teams in master_team_lists.items():
        if col in df.columns:
            df[col] = df[col].apply(lambda x: fuzzy_match_list(x, valid_teams))
            
    return df

def main():

    df = pd.read_csv("../data/Raw_User_Responses.csv")

    df.columns = ["timestamp", "consent", "fullname", "email", "venueFeatures", "MCBB", "WCBB", "NBA", "additionalComments"]

    df["email"] = df["email"].apply(clean_email)

    df = clean_basketball_survey_data(df)

    columns_to_master_lists = {
        "MCBB": CBB_TEAMS,
        "WCBB": CBB_TEAMS,
        "NBA": NBA_TEAMS
    }

    df = apply_fuzzy_matching(df, columns_to_master_lists, threshold=85)
    feedback = df[["additionalComments"]]
    df.drop(columns=["additionalComments"], inplace=True)

    df.to_csv("../data/User_Responses_Cleaned.csv", index=False)
    feedback.to_csv("../data/User_Feedback.csv", index=False)
    print("Data cleaning complete. Cleaned data saved to '../data/User_Responses_Cleaned.csv'.")
    print(df.head())

if __name__ == "__main__":
    main()