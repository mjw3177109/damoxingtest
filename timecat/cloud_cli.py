"""TimeCat V2 private local-first CLI. No credentials or private text in logs by default."""
import argparse
import json
import sys
from .cloud_memory import MemoryStore, SupabaseMemoryClient, synchronize, SyncError

def main(argv=None):
    p=argparse.ArgumentParser(description="TimeCat V2 private memory")
    p.add_argument("--db",default="timecat/private/timecat-v2.sqlite")
    sub=p.add_subparsers(dest="cmd",required=True)
    sub.add_parser("init");sub.add_parser("status");sub.add_parser("sync")
    x=sub.add_parser("propose")
    x.add_argument("kind",choices=["fact","lesson","goal","preference","event","experiment"])
    x.add_argument("content")
    x.add_argument("--source",required=True)
    x=sub.add_parser("review")
    x.add_argument("id");x.add_argument("decision",choices=["approve","reject"])
    x=sub.add_parser("recall")
    x.add_argument("query",nargs="?",default="");x.add_argument("--limit",type=int,default=10)
    args=p.parse_args(argv)
    db=MemoryStore(args.db)
    try:
        if args.cmd=="init": value={"initialized":True,"db":args.db}
        elif args.cmd=="status":value=db.counts()
        elif args.cmd=="propose":value={"pending_id":db.propose(args.kind,args.content,args.source)}
        elif args.cmd=="review":
            db.review(args.id,args.decision=="approve")
            value={"reviewed":args.id,"decision":args.decision}
        elif args.cmd=="recall":value=db.recall(args.query,args.limit)
        elif args.cmd=="sync":value=synchronize(db,SupabaseMemoryClient.from_environment())
        print(json.dumps(value,ensure_ascii=False,indent=2))
    except (SyncError, ValueError) as exc:
        print("TimeCat: "+str(exc),file=sys.stderr)
        return 2
    finally:db.close()
    return 0
if __name__=="__main__":
    sys.exit(main())
