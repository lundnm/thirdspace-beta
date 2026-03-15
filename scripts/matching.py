import pandas as pd
import ast
import re
import numpy as np
import random
from collections import Counter, defaultdict

TODAY = pd.to_datetime("today").date()

def simplify_team_name(name):
    """Helper function to strip formal academic words for better matching."""
    name = re.sub(r'(?i)^(the\s+)?university\s+of\s+', '', name)
    name = re.sub(r'(?i)\s+university$', '', name)
    name = re.sub(r'(?i)\s+college$', '', name)
    return name.strip()

def main():
    print("Loading data files...")
    today = pd.to_datetime("today").date()
    venues = pd.read_csv("../data/ThirdSpaceVenues.csv")
    users = pd.read_csv("../data/User_Responses_Cleaned.csv")
    streaming = pd.read_csv(f"../data/streaming_cleaned_{today}.csv")

    print("Calculating fanbase sizes and preferences...")
    # 1. Set up nested dictionary for fanbase stats
    fanbase_stats = {
        "NBA": defaultdict(lambda: {"size": 0, "features": Counter()}),
        "MCBB": defaultdict(lambda: {"size": 0, "features": Counter()}),
        "WCBB": defaultdict(lambda: {"size": 0, "features": Counter()})
    }

    # 2. Extract venue features and team sizes
    for index, row in users.iterrows():
        venue_str = row['venueFeatures']
        user_features = []
        if pd.notna(venue_str):
            user_features = [feature.strip() for feature in venue_str.split(",")]

        for sport in fanbase_stats.keys():
            teams_str = row[sport]
            if pd.notna(teams_str):
                user_teams = teams_str.split("; ")
                for team in user_teams:
                    fanbase_stats[sport][team]["size"] += 1
                    for feature in user_features:
                        fanbase_stats[sport][team]["features"][feature] += 1

    # 3. Flatten fanbase data
    flat_data = []
    for sport, teams in fanbase_stats.items():
        for team, stats in teams.items():
            most_common_feature = stats['features'].most_common(1)[0][0] if stats['features'] else None
            flat_data.append({
                "Sport": sport,
                "Team": team,
                "Fanbase_Size": stats["size"],
                "Most_Common_Venue_Feature": most_common_feature
            })
            
    fanbase_df = pd.DataFrame(flat_data).sort_values(by="Fanbase_Size", ascending=False).reset_index(drop=True)

    print("Mapping games to venues...")
    day_col_map = {0: 'open_Mon', 1: 'open_Tue', 2: 'open_Wed',
                   3: 'open_Thu', 4: 'open_Fri', 5: 'open_Sat', 6: 'open_Sun'}

    cable_channels = set([
        'ABC', 'CBS', 'NBC', 'Telemundo', 'USA Network',
        'ESPN', 'ESPN2', 'ESPN U', 'ESPNews', 'ESPN App',
        'CBS Sports Network', 'Big Ten Network', 'SEC Network', 'ACC Network',
        'NBA TV', 'NBC Sports Network', 
        'FanDuel Sports Network Detroit Extra',
        'Detroit SportsNet', 'Youtube TV'
    ])

    Sport_Team_lists = [row[["Sport", "Team", "Most_Common_Venue_Feature"]].tolist() for _, row in fanbase_df.iterrows()]
    games_venues_mappings = []
    assigned_venues = set()

    for sport, team, venue_feature in Sport_Team_lists:
        search_team = simplify_team_name(team)
        exact_match_pattern = rf"(?:^|,)\s*{re.escape(search_team.lower())}\s*(?:,|$)"
        
        matching_games = streaming[
            (streaming['League'] == sport) & 
            (streaming['Matchup'].str.lower().str.contains(exact_match_pattern, regex=True, na=False))
        ]
        
        if not matching_games.empty:
            game_venue_mapping = {
                "Sport": sport,
                "Team": team, 
                "Game": matching_games.iloc[0]['Matchup'],
                "Time": matching_games.iloc[0]['Time'],
                "Date": matching_games.iloc[0]['Date'],
                "Services": ast.literal_eval(matching_games.iloc[0]['Services']),
                "Venue_Feature": venue_feature
            }

            game_venue_mapping['Services'] = [
                "Cable" if service.strip() in cable_channels else service
                for service in game_venue_mapping['Services']
            ]

            def has_streaming(venue_services_str):
                if pd.isna(venue_services_str):
                    return False
                venue_services = [s.strip() for s in str(venue_services_str).split(',')]
                return any(service.strip() in venue_services for service in game_venue_mapping['Services'])

            game_time = game_venue_mapping['Time']
            open_col = day_col_map[pd.to_datetime(game_venue_mapping['Date']).dayofweek]

            def is_open(venue_row):
                open_time = str(venue_row[open_col])
                return open_time != 'CLOSED' and open_time <= game_time

            available_venues = venues[~venues['Name'].isin(assigned_venues)]
            available_venues = available_venues[available_venues.apply(is_open, axis=1)]
            
            vibe_match = available_venues[
                available_venues['Vibe'].str.lower().str.contains(str(venue_feature).lower(), regex=False, na=False)
            ]
            perfect_matches = vibe_match[vibe_match['StreamingServices'].apply(has_streaming)]

            if not perfect_matches.empty:
                selected_venue = random.choice(perfect_matches['Name'].tolist())
            else:
                fallback_matches = available_venues[available_venues['StreamingServices'].apply(has_streaming)]
                if not fallback_matches.empty:
                    selected_venue = random.choice(fallback_matches['Name'].tolist())
                else:
                    selected_venue = "No matching venue found"
            
            game_venue_mapping['Recommended_Venue'] = selected_venue
            if selected_venue != "No matching venue found":
                assigned_venues.add(selected_venue)
                
            games_venues_mappings.append(game_venue_mapping)

    final_mappings_df = pd.DataFrame(games_venues_mappings)

    print("Updating user database with daily assignments...")
    assigned_venues_list = []
    todays_games_list = []
    game_times_list = []

    for index, row in users.iterrows():
        user_mcbb = [t.strip() for t in str(row['MCBB']).split(';')] if pd.notna(row['MCBB']) else []
        user_wcbb = [t.strip() for t in str(row['WCBB']).split(';')] if pd.notna(row['WCBB']) else []
        user_nba = [t.strip() for t in str(row['NBA']).split(';')] if pd.notna(row['NBA']) else []
        
        user_venues = []
        user_games = []
        user_times = []
        seen_games = set() 
        
        for _, game_row in final_mappings_df.iterrows():
            sport = game_row['Sport']
            team = game_row['Team']
            venue = game_row['Recommended_Venue']
            game_matchup = game_row['Game']
            
            if venue == "No matching venue found":
                continue
                
            is_match = False
            if sport == 'MCBB' and team in user_mcbb:
                is_match = True
            elif sport == 'WCBB' and team in user_wcbb:
                is_match = True
            elif sport == 'NBA' and team in user_nba:
                is_match = True
                
            if is_match:
                if game_matchup not in seen_games: 
                    seen_games.add(game_matchup)
                    user_games.append(f"[{sport}] {game_matchup}")
                    user_times.append(game_row['Time'])
                    user_venues.append(venue)
        
        if user_games:
            assigned_venues_list.append("; ".join(user_venues))
            todays_games_list.append("; ".join(user_games))
            game_times_list.append("; ".join(user_times))
        else:
            assigned_venues_list.append(np.nan)
            todays_games_list.append(np.nan)
            game_times_list.append(np.nan)

    users['assigned_venues'] = assigned_venues_list
    users['todays_games'] = todays_games_list
    users['game_times'] = game_times_list

    # drop rows that don't have any game assignments for today
    users = users.dropna(subset=['todays_games']).reset_index(drop=True)

    print("Exporting finalized CSV...")
    users.to_csv(f"../data/User_Responses_With_Venues_{TODAY}.csv", index=False)
    print("Done! Data successfully saved to '../data/User_Responses_With_Venues.csv'")

if __name__ == "__main__":
    main()