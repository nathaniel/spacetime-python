"""Reader/writer for the Java ``Properties`` based .sce format."""
from __future__ import annotations
from pathlib import Path
from .properties import read_properties, write_properties
from ..model.scenario import Scenario
from ..model.objects import Clock, Flash
from ..model.worldline import Worldline, WorldlineRecord
from ..model.events import Event
from ..model.decorations import Interval, LightCone, Hyperbola
from ..model.lorentz import inverse_transform, transform

def load_scenario(path: str | Path) -> Scenario:
    """Load a scenario from a Java-compatible properties file."""
    p = read_properties(Path(path)); sc = Scenario(float(p.get("betaRel", 0)), float(p.get("t", 0)))
    sc.comments = p.get("comments", "")
    sc.view_xmin, sc.view_xmax = float(p.get("sx1", -5)), float(p.get("sx2", 5))
    for name in p.get("objects", "").split():
        prefix = name + "."
        cls = p.get(prefix+"class", "STClock")
        values = [float(v) for v in p.get(prefix+"worldlineData", "").split()]
        records = [WorldlineRecord.from_frame(*values[i:i+4], sc.beta_rel) for i in range(0, len(values), 4)]
        if not records: records = [WorldlineRecord(0, 0, 0, 0)]
        obj_cls = Flash if cls.endswith("STFlash") else Clock
        obj = obj_cls(name, p.get(prefix+"label", name), p.get(prefix+"note", ""), Worldline(records),
                      kind="flash" if obj_cls is Flash else "clock")
        obj.worldline.has_birth = p.get(prefix+"hasBirth", "false") == "true"
        obj.worldline.has_termination = p.get(prefix+"hasTermination", "false") == "true"
        sc.objects.append(obj)
    for name in p.get("events", "").split():
        q=name+"."; cls=p.get(q+"class","")
        x, t = inverse_transform(float(p.get(q+"x", 0)), float(p.get(q+"t", 0)), sc.beta_rel)
        event=Event(name, x, t, p.get(q+"label", name), p.get(q+"note", ""))
        event.beta_change = cls.endswith("STBetaChangeEvent")
        event.placed_at_worldline=p.get(q+"isPlacedAtWorldline","false")=="true"; event.fixed_at_intersection=p.get(q+"isFixedAtIntersection","false")=="true"
        event.object_name=p.get(q+"d") or None; event.intersection_names=tuple(x for x in (p.get(q+"d1"),p.get(q+"d2")) if x) or None
        event.boundary=p.get(q+"boundary") or None
        sc.events.append(event)
    for name in p.get("decorations", "").split():
        q=name+"."; cls=p.get(q+"class","")
        def event(key: str) -> Event | None:
            """Resolve a decoration event reference by property key."""
            n=p.get(q+key,""); return sc.event(n) if n else None
        if cls.endswith("STLightCone"): d=LightCone(name=name,event=event("ev"))
        elif cls.endswith("STHyperbola"): d=Hyperbola(name=name,event=event("ev"))
        else: d=Interval(name=name,first=event("ev1"),second=event("ev2"))
        sc.decorations.append(d)
    sc.synchronize_boundary_events()
    known={"betaRel","t","comments","sx1","sx2","objects","events","decorations","eventCounter","clockCounter","flashCounter","decorationCounter"}
    sc.unknown_properties={k:v for k,v in p.items() if k not in known}
    return sc

def save_scenario(scenario: Scenario, path: str | Path) -> None:
    """Save a scenario to a Java-compatible properties file."""
    p=dict(scenario.unknown_properties)
    p.update(betaRel=f"{scenario.beta_rel:.9g}", t=f"{scenario.time:.9g}", comments=scenario.comments,
             sx1=f"{scenario.view_xmin:.9g}", sx2=f"{scenario.view_xmax:.9g}",
             objects=" ".join(o.name for o in scenario.objects), events=" ".join(e.name for e in scenario.events),
             decorations=" ".join(d.name for d in scenario.decorations))
    p.update(eventCounter=str(len(scenario.events)+1), clockCounter=str(sum(isinstance(o,Clock) for o in scenario.objects)+1),
             flashCounter=str(sum(isinstance(o,Flash) for o in scenario.objects)+1), decorationCounter=str(len(scenario.decorations)+1))
    for o in scenario.objects:
        q=o.name+"."; p.update({q+"name":o.name,q+"label":o.label,q+"note":o.note,q+"class":"spacetime.STFlash" if isinstance(o,Flash) else "spacetime.STClock",
          q+"hasBirth":str(o.worldline.has_birth).lower(),q+"hasTermination":str(o.worldline.has_termination).lower()})
        vals=[]
        for r in o.worldline.records: vals += [f"{x:.9g}" for x in r.in_frame(scenario.beta_rel)]
        p[q+"worldlineData"]=" ".join(vals)
    for e in scenario.events:
        q=e.name+"."; p.update({q+"name":e.name,q+"label":e.label,q+"note":e.note,q+"class":"spacetime.STBetaChangeEvent" if e.beta_change else "spacetime.STEvent",
          q+"x":f"{transform(e.x,e.t,scenario.beta_rel)[0]:.9g}",q+"t":f"{transform(e.x,e.t,scenario.beta_rel)[1]:.9g}",
          q+"isPlacedAtWorldline":str(e.placed_at_worldline).lower(),q+"isFixedAtIntersection":str(e.fixed_at_intersection).lower(),
          q+"d":e.object_name or "",q+"d1":e.intersection_names[0] if e.intersection_names else "",q+"d2":e.intersection_names[1] if e.intersection_names else "",
          q+"boundary":e.boundary or ""})
    for d in scenario.decorations:
        q=d.name+"."; p[q+"class"]="spacetime.ST"+({"interval":"Interval","lightcone":"LightCone","hyperbola":"Hyperbola"}[d.kind])
        if isinstance(d,Interval): p.update({q+"ev1":d.first.name if d.first else "",q+"ev2":d.second.name if d.second else ""})
        else: p[q+"ev"]=d.event.name if d.event else ""
    write_properties(Path(path), p)
