#!/usr/bin/env python3
"""Robô do Raio-X de Hortolândia.

Coleta os dados públicos do sistema legislativo da Câmara Municipal de Hortolândia
(SAPL) e gera site/dados.js. Se a coleta vier incompleta ou estranha, o robô para
com erro e o site continua com a última versão boa.

Uso:
  python robo/atualizar.py              # coleta tudo e monta
  python robo/atualizar.py --so-montar  # monta a partir do cache já baixado
"""
import collections, datetime, json, os, re, sys, time, unicodedata, urllib.request
from concurrent.futures import ThreadPoolExecutor
from zoneinfo import ZoneInfo

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(RAIZ, "cache")
SAIDA = os.path.join(RAIZ, "site", "dados.js")
RESUMO = os.path.join(RAIZ, "site", "resumo.json")
UA = "Mozilla/5.0 (compatible; RaioXHortolandia/1.0; projeto civico; +https://github.com/gabrisantos1-stack/olhonaptlandia)"
BASE = "https://sapl.hortolandia.sp.leg.br"
API = BASE + "/@@vereadores"
HOJE = datetime.datetime.now(ZoneInfo("America/Sao_Paulo")).date()
INICIO = "2025-01-01"                      # início da legislatura 2025-2028
ANOS = list(range(2025, min(HOJE.year, 2028) + 1))

# Nome pelo qual cada vereador é conhecido. Sem entrada aqui, aparece o nome civil.
APELIDOS = {
    "Aldemir Clemente da Silva": "Aldemir Clemente", "Ananias José Barbosa": "Ananias",
    "Carlos Rodrigues de Oliveira": "Carlão do Nova Europa", "Cicero Cesar Brasil": "Cesinha Brasil",
    "Claudinei Prazeres de Barros": "Nei Prazeres", "Clemilton Alves da Silva": "Clemilton Silva",
    "Clodoaldo Santos da Silva": "Clodoaldo", "Daniel Laranjeira": "Daniel Laranjeira",
    "Derli de Jesus Athanazio Bueno": "Derli", "Dionata Domingues": "Dionatan Domingues",
    "Edimilson Marcelo Afonso": "Zaca", "Edivaldo Sousa Araújo": "Edivaldo Araújo",
    "Edvam Campos de Albuquerque": "Ceará", "Luiz Carlos Silva Meira": "Luiz Regional",
    "Paulo Pereira Filho": "Paulão", "Reginaldo Roberto Rodrigues da Costa": "Régis da Serralheria",
    "Roberta Morais Diniz": "Professora Roberta Diniz", "Sidney Eloi Vianna": "Sidney Cabrito",
    "Valdecir Alves Pereira": "Nego",
}
# Subsídio mensal bruto, igual para todos. Valor fixo: não vem da API.
SALARIO = dict(v=16503, lei="Lei nº 4.213/2023",
               u=BASE + "/consultas/norma_juridica/norma_juridica_mostrar_proc?cod_norma=18122")


def nm(s):
    return "".join(c for c in unicodedata.normalize("NFD", s.lower()) if unicodedata.category(c) != "Mn")


def get(url, tries=5):
    err = None
    for t in range(tries):
        try:
            r = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(r, timeout=90) as f:
                return json.load(f)
        except Exception as e:  # rede instável ou servidor ocupado: espera e tenta de novo
            err = e
            time.sleep(3 + 4 * t)
    raise RuntimeError(f"falha ao buscar {url}: {err!r}")


# ------------------------------------------------------------------ coleta
def coletar_um(vid):
    rec = {}
    base = get(f"{API}/{vid}?page_size=5")
    rec["base"] = {k: v for k, v in base.items()
                   if k not in ("proposicoes", "relatorias", "frequencia", "votacoes", "image", "labels", "ui")}
    rec["prop_xy"] = base["proposicoes"]["facets"].get("xy")
    rec["relatorias_xy"] = base["relatorias"]["facets"].get("xy")
    rec["freq"] = {}
    for ano in ANOS:
        d = get(f"{API}/{vid}?page_size=50&ano_frequencia={ano}")["frequencia"]
        items, tot, pg = d["items"], d["total"], 1
        while len(items) < tot and pg < 20:
            pg += 1
            items += get(f"{API}/{vid}?page_size=50&ano_frequencia={ano}&page_frequencia={pg}")["frequencia"]["items"]
        rec["freq"][str(ano)] = dict(resumo=d.get("resumo"), total=tot, items=[
            dict(s=i["sessao_id"], d=i["data_sessao"], t=i["tipo_sessao"], n=i["identificacao_sessao"],
                 f=i["frequencia"], u=i["@id"]) for i in items])
    vots, pg = [], 1
    while True:  # mais recentes primeiro; para ao sair da legislatura
        v = get(f"{API}/{vid}?page_size=50&page_votacoes={pg}")["votacoes"]
        its = v["items"]
        if not its:
            break
        vots += [dict(id=i["id"], t=i["title"], d=i["data_sessao"], v=i["voto_classe"], a=i.get("autoria", ""),
                      e=i.get("ementa", "")[:300], u=i.get("materia_href")) for i in its]
        if its[-1]["data_sessao"] < INICIO or len(vots) >= v["total"]:
            break
        pg += 1
    rec["votacoes"] = [x for x in vots if x["d"] >= INICIO]
    props = []
    for ano in ANOS:
        pg = 1
        while True:
            d = get(f"{API}/{vid}?page_size=50&ano_proposicoes={ano}&page_proposicoes={pg}")["proposicoes"]
            its = d["items"]
            props += [dict(id=i["id"], t=i["title"], e=i.get("ementa", ""), d=i.get("data_apresentacao", ""),
                           tp=i.get("tipo", ""), k=i.get("item_kind", ""), r=i.get("ultima_votacao_resultado", ""))
                      for i in its]
            if not its or pg * 50 >= d["total"]:
                break
            pg += 1
    rec["props"] = props
    json.dump(rec, open(os.path.join(CACHE, f"v{vid}.json"), "w"), ensure_ascii=False)
    print(f"  coletado {vid} {rec['base']['title']}: {len(rec['votacoes'])} votos, {len(props)} propostas", flush=True)


def coletar():
    os.makedirs(CACHE, exist_ok=True)
    for f in os.listdir(CACHE):
        os.remove(os.path.join(CACHE, f))
    lista = get(API)
    json.dump(lista, open(os.path.join(CACHE, "lista.json"), "w"), ensure_ascii=False)
    ids = [i["id"] for i in lista["items"]]
    print(f"{len(ids)} vereadores na lista da Câmara", flush=True)
    with ThreadPoolExecutor(3) as ex:  # 3 por vez, para não pesar no servidor da Câmara
        list(ex.map(coletar_um, ids))


# ------------------------------------------------------------------ classificação
HOM_M = re.compile(r"mocao de (pesar|parabeniza|congratula|aplauso|louvor|reconhecimento|agradecimento|homenagem|merito|honra|gratidao|felicita|elogio)")
HOM_T = re.compile(r"titulo (de )?cidad|titulo honor|medalha|diploma|honorific|denominac|denomina |denomina-se|da nome|institui o dia |institui a semana|institui o mes |dia municipal d|semana municipal d|calendario oficial|data comemorativa")
LEIS = ("Projeto de Lei", "Projeto de Lei Complementar", "Proposta de Emenda à Lei Orgânica do Município",
        "Substitutivo", "Emenda Modificativa", "Emenda Supressiva", "Emenda Aditiva", "Emenda Substitutiva")


def grupo(i):
    """b = pedido no bairro, c = cobrança, h = homenagem, l = proposta de lei, o = outros."""
    e, tp = nm(i["e"]), i["tp"]
    if tp == "Indicação":
        return "b"
    if tp == "Requerimento":
        return "c"
    if tp == "Moção":
        if HOM_M.search(e):
            return "h"
        return "c" if "mocao de apelo" in e else "o"
    if HOM_T.search(e):
        return "h"
    return "l" if tp in LEIS else "o"


PRE = r"(?:Jardim|Jd\.?|Parque|Pq\.?|Vila|Residencial|Res\.|Chácaras?|Chacaras?|Loteamento|Núcleo|Conjunto Habitacional|Condomínio|Recanto|Remanso|Nova|Novo)"
W = r"(?:[A-ZÁÉÍÓÚÂÊÔÃÕÇ][\wáéíóúâêôãõçÁÉÍÓÚÂÊÔÃÕÇ'’]*|I{1,3}|IV|V|\d{1,2})"
RX_BAIRRO = re.compile(rf"\b({PRE})\s+({W}(?:\s+(?:(?:de|da|do|dos|das|e)\s+)?{W}){{0,4}})")
ALIAS = {"jd": "Jardim", "jd.": "Jardim", "pq": "Parque", "pq.": "Parque", "res.": "Residencial",
         "chacaras": "Chácaras", "chacara": "Chácara"}


# ------------------------------------------------------------------ montagem
def montar():
    lista = json.load(open(os.path.join(CACHE, "lista.json")))
    recs = [json.load(open(os.path.join(CACHE, f"v{i['id']}.json"))) for i in lista["items"]]
    hoje = HOJE.isoformat()

    sess, meta = collections.defaultdict(dict), {}
    for r in recs:
        for a in r["freq"].values():
            for i in a["items"]:
                sess[i["s"]][r["base"]["id"]] = i["f"]
                meta[i["s"]] = dict(d=i["d"], n=i["n"], u=i["u"])
    # sessão em que ninguém tem presença registrada: o dado não existe, não é falta
    semreg = [s for s in sess if not any(v == "P" for v in sess[s].values())]
    valid = sorted((s for s in sess if s not in semreg), key=lambda s: (meta[s]["d"], int(s)))

    vot, vmeta = collections.defaultdict(dict), {}
    for r in recs:
        for v in r["votacoes"]:
            vot[v["id"]][r["base"]["id"]] = v["v"]
            vmeta[v["id"]] = v
    unan = sum(1 for x in vot.values() if len(set(x.values())) == 1)

    V = []
    for r in recs:
        b, vid = r["base"], r["base"]["id"]
        m = [x for x in b["mandatos"] if x["legislatura_ano_inicio"] == 2025][0]
        mesa = [x["title"] for x in b.get("mesas", []) if x["start"] <= hoje <= x["end"]]
        fr = collections.Counter(sess[s].get(vid, "-") for s in valid)
        vc = collections.Counter(v["v"] for v in r["votacoes"])
        naos = sorted((dict(t=v["t"], d=v["d"], e=v["e"], u=v["u"], v=v["v"],
                            a=v["a"] if v["a"] in ("Poder Executivo", "Mesa Diretora") else "Vereador(es)")
                       for v in r["votacoes"] if v["v"] != "sim"), key=lambda x: x["d"], reverse=True)
        V.append(dict(id=vid, nome=b["title"], ap=APELIDOS.get(b["title"], b["title"]),
                      part=b["partido_atual"]["sgl"], votos=m["votos"], ini=m["start"],
                      mesa=mesa[0] if mesa else "", P=fr["P"], A=fr["A"], F=fr["F"],
                      vs=vc["sim"], vn=vc["nao"], va=vc["abstencao"], naos=naos,
                      cat={k: 0 for k in "bchlo"},
                      url=f"{BASE}/consultas/parlamentar/parlamentar_mostrar_proc?cod_parlamentar={vid}"))
    V.sort(key=lambda x: x["nome"])
    idx = {v["id"]: n for n, v in enumerate(V)}

    itens = {}
    for r in recs:
        for i in r["props"]:
            key = (i["k"], i["id"])
            if key not in itens:
                d = i["d"].split("/")
                itens[key] = dict(i=i["id"], t=i["t"], e=i["e"].strip(), d=d[2] + d[1] + d[0], c=grupo(i),
                                  r="" if i["r"] == "Lido em Plenário" else i["r"], a=[],
                                  m=1 if i["k"] == "materia" else 0)
            itens[key]["a"].append(idx[r["base"]["id"]])
    L = sorted(itens.values(), key=lambda x: x["d"], reverse=True)
    for it in L:
        for a in it["a"]:
            V[a]["cat"][it["c"]] += 1

    bc, disp = collections.Counter(), {}
    for it in L:
        vistos = set()
        for mt in RX_BAIRRO.finditer(it["e"]):
            nome = (ALIAS.get(mt.group(1).lower(), mt.group(1)) + " " + mt.group(2)).strip()
            k = nm(nome)
            if k not in vistos:
                vistos.add(k)
                bc[k] += 1
                disp.setdefault(k, collections.Counter())[nome] += 1
    bairros = [disp[k].most_common(1)[0][0] for k, n in bc.most_common(400) if n >= 8]

    D = dict(ger=hoje, ult=max(meta[s]["d"] for s in valid),
             sess=[dict(d=meta[s]["d"]) for s in valid], semreg=[dict(d=meta[s]["d"], n=meta[s]["n"]) for s in semreg],
             nvot=len(vot), unan=unan, v=V,
             items=[[it["i"], it["t"], it["e"], it["d"], it["c"], it["r"], it["a"], it["m"]] for it in L],
             catot=dict(collections.Counter(it["c"] for it in L)), bairros=bairros, sal=SALARIO)

    resumo = dict(data=hoje, vereadores=len(V), propostas=len(L), sessoes=len(valid), votacoes=len(vot),
                  ultima_sessao=D["ult"])
    conferir(D, resumo)
    os.makedirs(os.path.dirname(SAIDA), exist_ok=True)
    s = json.dumps(D, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    open(SAIDA, "w").write("window.RX=" + s + ";")
    json.dump(resumo, open(RESUMO, "w"), ensure_ascii=False, indent=1)
    print("publicado:", resumo, flush=True)


def conferir(D, novo):
    """Trava de segurança: se algo estiver estranho, para aqui e nada é publicado."""
    erros = []
    if not 17 <= novo["vereadores"] <= 21:
        erros.append(f"{novo['vereadores']} vereadores (esperado: 19)")
    for v in D["v"]:
        if v["P"] + v["A"] + v["F"] == 0:
            erros.append(f"{v['nome']} sem nenhuma sessão registrada")
    if os.path.exists(RESUMO):
        ant = json.load(open(RESUMO))
        for k in ("propostas", "sessoes", "votacoes"):
            if novo[k] < ant[k] * 0.98:
                erros.append(f"{k} caiu de {ant[k]} para {novo[k]}")
    else:
        for k, minimo in (("propostas", 5000), ("sessoes", 50), ("votacoes", 500)):
            if novo[k] < minimo:
                erros.append(f"{k} = {novo[k]}, abaixo do mínimo {minimo}")
    if erros:
        sys.exit("COLETA REJEITADA, site mantido como estava:\n - " + "\n - ".join(erros))


if __name__ == "__main__":
    if "--so-montar" not in sys.argv:
        coletar()
    montar()
