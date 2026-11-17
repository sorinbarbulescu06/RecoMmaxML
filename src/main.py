import argparse
import sys
from src.base.pipeline import run_pipeline_logic

def main():
    parser = argparse.ArgumentParser(description="RecomMaxML")
    parser.add_argument("--file", type=str, help="Pathway to the query file")
    args = parser.parse_args()

    if args.file:
        try:
            with open(args.file, "r", encoding="utf-8") as f:
                # Citim fisierul si generam lista fix cum vrea pipeline-ul
                test_queries = [line.strip() for line in f if line.strip()]
            
            print(f"-> Loaded {len(test_queries)} queries from {args.file}. Starting the process...\n")
            run_pipeline_logic(test_queries)
            
        except FileNotFoundError:
            print(f"[ERROR] File '{args.file}' was not found.")
            sys.exit(1)
            
    else:
        print("=" * 70)
        print(" Interactive mode - RecomMaxML")
        print(" Input query and press ENTER (or 'exit' for leaving).")
        print("=" * 70)
        
        while True:
            try:
                user_input = input("\n> Input querry: ").strip()
                
                if user_input.lower() in ['exit', 'quit']:
                    print("Exiting process..")
                    break
                    
                if not user_input:
                    continue
                
                print("") # Un spatiu estetic inainte de printul de la pipeline
                
                # Trimitem pur si simplu o lista cu acel string catre pipeline-ul tau
                test_queries = [user_input]
                run_pipeline_logic(test_queries)
                
            except KeyboardInterrupt:
                print("\nForced exit...")
                break

if __name__ == "__main__":
    main()