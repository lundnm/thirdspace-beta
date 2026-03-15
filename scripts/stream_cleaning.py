import pandas as pd

TODAY = pd.to_datetime("today").date()

def clean_streaming_data(date):
    
    streaming_df = pd.read_csv(f"../data/livesports_schedule_{date}.csv")

    streaming_df["Time"] = pd.to_datetime(streaming_df["Time"], format="%I:%M %p").dt.strftime("%H:%M")

    streaming_df["League"] = streaming_df["League"].str.strip()

    streaming_df["Matchup"] = streaming_df["Matchup"].str.strip(" @").str.replace(" @ ", ",")

    streaming_df["Services"] = streaming_df["Services"].str.split(", ")

    streaming_exploded = streaming_df.explode("Services")

    available_in_detroit = {
        # National Cable & Broadcast Networks
        'ABC', 'CBS', 'NBC', 'Telemundo', 'USA Network',
        'ESPN', 'ESPN2', 'ESPN U', 'ESPNews', 'ESPN App',
        'CBS Sports Network', 'Big Ten Network', 'SEC Network', 'ACC Network',
        'NBA TV', 'NBC Sports Network', # NBCSN is defunct, but was national
        
        # National Streaming Platforms
        'Peacock', 'Prime Video', 'Paramount+', 'Fubo Sports',
        'ESPN Select', 'ESPN Unlimited', 'NBA League Pass',
        
        # Local to Detroit / Michigan
        'FanDuel Sports Network Detroit Extra',
        'Detroit SportsNet'
    }

    streaming_exploded_filterd = streaming_exploded[streaming_exploded["Services"].isin(available_in_detroit)]

    streaming_cleaned = streaming_exploded_filterd.groupby(streaming_exploded_filterd.index).agg({
    'Date': 'first',
    'Time': 'first',
    'League': 'first',
    'Matchup': 'first',
    'Services': lambda x: list(x)
    }).reset_index(drop=True)

    streaming_cleaned['DayOfWeek'] = pd.to_datetime(streaming_cleaned['Date']).dt.day_name()



    streaming_cleaned.to_csv(f"../data/streaming_cleaned_{date}.csv", index=False)
    print(f"Data cleaning complete. Cleaned data saved to '../data/streaming_cleaned_{date}.csv'.")

def main():
    clean_streaming_data(TODAY)

if __name__ == "__main__":
    main()

