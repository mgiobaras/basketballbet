"""Candidate and original receive identical quotes, preserve saved history."""
import json,sys,tempfile,os
from pathlib import Path
from datetime import datetime,timedelta,timezone
from copy import deepcopy
from unittest.mock import patch
from streamlit.testing.v1 import AppTest
from check_basketball import quote
from basketball_store import Store

def main(root):
 rows=json.loads((root/'replay.json').read_text());row=[r for r in rows if r['game']['season']==2026][400];f=deepcopy(row['game']);before=datetime.fromisoformat(f['kickoff']);now=datetime.now(timezone.utc);shift=now+timedelta(days=2)-before
 games=[deepcopy(g) for g in json.loads((root/'games.json').read_text()) if datetime.fromisoformat(g['kickoff'])<before-timedelta(days=4)]
 for g in games:g['kickoff']=(datetime.fromisoformat(g['kickoff'])+shift).isoformat()
 f.update(kickoff=(before+shift).isoformat(),status='NS',score={'home':None,'away':None});q=quote(f,now=now)
 with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{'BET_DB_PATH':d+'/test.sqlite3','SUPABASE_URL':'','SUPABASE_SERVICE_ROLE_KEY':'','REQUIRE_REMOTE_DB':'false','APP_PASSWORD':''}),patch('basketball_data.BasketballData.fixtures',return_value=[f]),patch('basketball_data.BasketballData.history',return_value=games),patch('basketball_data.BasketballData.quotes',return_value=([q],[])),patch('nba_model.league_history',return_value=games):
  app=AppTest.from_file(str(Path(__file__).parent/'app.py')).run(timeout=30)
  next(s for s in app.selectbox if s.label=='Μοντέλο υπολογισμού').select_index(2).run(timeout=30)
  next(b for b in app.button if b.label.startswith('Υπολογισμός')).click().run(timeout=30)
  assert not app.exception
  store=Store(d+'/test.sqlite3');logs=store.list_predictions();assert len(logs)==2 and store.list()==[]
  candidate=next(r for r in logs if r['payload']['model'].get('candidate_only'));baseline=next(r for r in logs if r['payload']['model'].get('comparison_role'))
  assert candidate['payload']['markets']['over']['quote']==baseline['payload']['markets']['over']['quote']
  assert candidate['payload']['model']['recommendation_policy']['recommended_market'] is None
  assert candidate['payload']['model']['input_games']==baseline['payload']['model']['input_games']
 print('PASS NBA UI: experimental selector, identical price/input snapshots, original/candidate independent logs, failed gate blocks primary tips, user history unchanged')
if __name__=='__main__':main(Path(sys.argv[1]))
