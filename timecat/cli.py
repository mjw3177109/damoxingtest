"""Usage: python -m timecat.cli --db /path/to/private/state.sqlite <command>."""
import argparse
import json
from pathlib import Path
from . import core

def main(argv=None):
    parser=argparse.ArgumentParser(description="TimeCat verified-memory prototype")
    parser.add_argument("--db",default="timecat/private/timecat.sqlite")
    sub=parser.add_subparsers(dest="cmd",required=True)
    sub.add_parser("init");sub.add_parser("status")
    p=sub.add_parser("record");p.add_argument("kind",choices=sorted(core.ALLOWED));p.add_argument("content");p.add_argument("--source",required=True);p.add_argument("--key")
    p=sub.add_parser("propose");p.add_argument("kind",choices=sorted(core.ALLOWED));p.add_argument("content");p.add_argument("--source",required=True);p.add_argument("--supersedes",type=int)
    p=sub.add_parser("review");p.add_argument("id",type=int);p.add_argument("decision",choices=["approve","reject"])
    p=sub.add_parser("recall");p.add_argument("query",nargs="?",default="");p.add_argument("--limit",type=int,default=10)
    p=sub.add_parser("reflect");p.add_argument("period");p.add_argument("summary")
    args=parser.parse_args(argv)
    db=core.connect(Path(args.db))
    try:
        if args.cmd=="init":out={"initialized":str(args.db)}
        elif args.cmd=="status":out=core.snapshot(db)
        elif args.cmd=="record":out=core.record(db,args.kind,args.content,args.source,args.key)
        elif args.cmd=="propose":out={"proposed_id":core.propose(db,args.kind,args.content,args.source,args.supersedes)}
        elif args.cmd=="review":core.review(db,args.id,args.decision=="approve");out={"reviewed_id":args.id,"decision":args.decision}
        elif args.cmd=="recall":out=core.recall(db,args.query,args.limit)
        elif args.cmd=="reflect":out={"reflection_id":core.propose_reflection(db,args.period,args.summary)}
        print(json.dumps(out,ensure_ascii=False,indent=2))
    finally:db.close()
if __name__=="__main__":main()
