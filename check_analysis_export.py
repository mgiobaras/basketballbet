"""Read-only private export, including unselected predictions and pending writes."""
from contextlib import nullcontext
from copy import deepcopy
import json
from unittest.mock import Mock

from prediction_log import analysis_export


class UI:
    def __init__(self):
        self.session_state={};self.clicked=False;self.files=[];self.messages=[]
    def expander(self,*args,**kwargs):return nullcontext()
    def button(self,*args,**kwargs):return self.clicked
    def caption(self,message):self.messages.append(message)
    def info(self,message):self.messages.append(message)
    def error(self,message):self.messages.append(message)
    def download_button(self,label,data,filename,*args,**kwargs):self.files.append((filename,json.loads(data)))


def main():
    for sport in ['football','basketball']:
        st=UI();store=Mock()
        log={'id':'persisted','sport':sport,'captured_at':'2026-11-08T10:00:00Z',
             'payload':{'markets':{'1':{'probability':.6},'2':{'probability':.4},'over':{'probability':.55}}}}
        pending=dict(deepcopy(log),id='pending')
        bets=[{'id':'chosen','market':'1','legacy_absences':{'home':1}}]
        original=deepcopy(bets)
        store.list.return_value=bets;store.list_predictions.return_value=[log]
        st.session_state['pending_prediction_log:'+sport]={'persisted':log,'pending':pending}
        analysis_export(st,store,sport)
        store.list.assert_not_called();store.list_predictions.assert_not_called()
        assert not st.files
        st.clicked=True
        analysis_export(st,store,sport)
        name,packet=st.files[-1]
        assert name==sport+'_analysis_backup.json' and packet['sport']==sport
        assert packet['selected_bets']==original and bets==original
        assert packet['prediction_log']==[log] and packet['pending_prediction_log']==[pending]
        assert '2' in packet['prediction_log'][0]['payload']['markets']  # Unselected outcome preserved.
        assert st.session_state['pending_prediction_log:'+sport]=={'persisted':log,'pending':pending}
        assert not store.record_prediction.called
        store.list_predictions.assert_called_once_with(sport)
        st.files=[];store.list_predictions.side_effect=RuntimeError('controlled read failure')
        analysis_export(st,store,sport)
        assert not st.files and 'analysis_export:'+sport not in st.session_state
        assert any('controlled read failure' in m for m in st.messages)
    print('PASS private export: explicit owner action only, predictions beyond chosen bets, all original history, pending dedupe, no writes, read errors clear stale downloads')


if __name__=='__main__':main()
