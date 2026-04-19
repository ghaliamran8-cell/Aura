import asyncio

def test_ddg():
    try:
        from duckduckgo_search import DDGS
        results = DDGS().chat("Bonjour, es-tu là ?", model='gpt-4o-mini')
        print("DDG Chat Response:", results)
        
        # Test web search
        search = list(DDGS().text("Python", max_results=2))
        print("Search:", search)
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    test_ddg()
