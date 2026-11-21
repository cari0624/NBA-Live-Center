import json, os, urllib.request, datetime, time
from zoneinfo import ZoneInfo
from pathlib import Path
BASE='https://site.api.espn.com/apis/site/v2/sports/basketball/nba'
OUT=Path('data'); OUT.mkdir(exist_ok=True)
def get(path):
    req=urllib.request.Request(BASE+path,headers={'User-Agent':'Mozilla/5.0 (NBA Live Center; stats dashboard)'})
    with urllib.request.urlopen(req,timeout=25) as r: return json.load(r)
def write(name,obj): (OUT/name).write_text(json.dumps(obj,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
def parse_num(v):
    try:return int(float(str(v).replace(',','')))
    except:return None

def main():
    now=datetime.datetime.now(ZoneInfo('America/Chicago'))
    teams_data=get('/teams?limit=50')
    teams=[]; players={}; errors=[]
    for league in teams_data.get('sports',[]):
      for lg in league.get('leagues',[]):
       for item in lg.get('teams',[]):
        t=item.get('team',{}); abbr=t.get('abbreviation'); tid=t.get('id')
        if not abbr or not tid:continue
        teams.append({'id':str(tid),'abbr':abbr,'name':t.get('displayName',abbr)})
        try:
          roster=get(f'/teams/{tid}/roster')
          arr=[]
          for a in roster.get('athletes',[]):
            if 'items' in a:arr.extend(a['items'])
            elif a.get('id'):arr.append(a)
          players[abbr]=[{'id':str(a['id']),'name':a.get('displayName') or a.get('fullName') or 'Jugador'} for a in arr if a.get('id')]
        except Exception as e: errors.append(f'roster {abbr}: {e}'); players[abbr]=[]
        time.sleep(.07)
    # Read recent NBA final game box scores. One box score contains both teams' player shooting stats.
    games={}; seen=set()
    for days_back in range(0,31):
      day=(now.date()-datetime.timedelta(days=days_back)).strftime('%Y%m%d')
      try: score=get(f'/scoreboard?dates={day}&limit=30')
      except Exception as e:errors.append(f'scoreboard {day}: {e}');continue
      for event in score.get('events',[]):
        eid=str(event.get('id',''))
        if not eid or eid in seen:continue
        seen.add(eid)
        comp=(event.get('competitions') or [{}])[0]
        if not comp.get('status',{}).get('type',{}).get('completed',False):continue
        try:
          summary=get(f'/summary?event={eid}')
          b=summary.get('boxscore',{})
          for side in b.get('players',[]):
            abbr=side.get('team',{}).get('abbreviation','')
            others=[x.get('team',{}).get('abbreviation','') for x in b.get('players',[]) if x is not side]
            opponent=others[0] if others else '?'
            for section in side.get('statistics',[]):
              labels=section.get('labels',[])
              names=section.get('names',[])
              idx=next((i for i,v in enumerate(names) if str(v).lower() in ('threepointfieldgoalsmade-threepointfieldgoalsattempted','3pt','3pm-3pa')),None)
              if idx is None:idx=next((i for i,v in enumerate(labels) if str(v).upper() in ('3PT','3PM-3PA','3P')),None)
              if idx is None:continue
              for a in section.get('athletes',[]):
                aid=str(a.get('athlete',{}).get('id',''))
                stats=a.get('stats',[])
                if not aid or idx>=len(stats):continue
                raw=str(stats[idx]); parts=raw.split('-')
                if len(parts)!=2:continue
                made,attempted=map(parse_num,parts)
                if made is None or attempted is None:continue
                games.setdefault(aid,[]).append({'date':event.get('date','')[:10],'opponent':opponent,'team':abbr,'made':made,'attempted':attempted,'gameId':eid})
          time.sleep(.07)
        except Exception as e:errors.append(f'game {eid}: {e}')
    for aid,items in games.items():
      games[aid]=sorted(items,key=lambda x:(x['date'],x['gameId']),reverse=True)[:10]
    # Do not overwrite prior valid dataset with an empty or incomplete upstream response.
    if len(teams)<25:raise RuntimeError(f'Only {len(teams)} teams received')
    if len(games)<50:raise RuntimeError(f'Only {len(games)} player game records received; preserving prior data')
    write('nba.json',{'updatedAt':now.isoformat(),'season':'2026-27','teams':sorted(teams,key=lambda t:t['name']),'rosters':players,'games':games,'warnings':errors[:15]})
    print('Updated',len(teams),'teams',len(games),'players',len(errors),'warnings')
if __name__=='__main__':main()
