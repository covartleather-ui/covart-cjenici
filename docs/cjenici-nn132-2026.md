# Covart – pravilnici NN 132/2026 (primjena od 17. 11. 2026.)

Izvori:
- [Pravilnik o načinu objave cjenika proizvoda (NN 132/2026, 1584)](https://narodne-novine.nn.hr/clanci/sluzbeni/2026_11_132_1584.html)
- [Pravilnik o isticanju bazne cijene proizvoda (NN 132/2026, 1583)](https://narodne-novine.nn.hr/clanci/sluzbeni/2026_11_132_1583.html)

## Izlaz

Generator je jedini izvor CSV/XML datoteka; izvorne cijene i bazne cijene preuzimaju se iz Shopifyja, bez izmišljanja povijesnih cijena.

- **Roba (12 stupaca):** naziv, šifra, marka, neto količina (ako je primjenjivo), jedinica mjere, maloprodajna cijena, oznaka posebnog oblika prodaje, naziv posebnog oblika prodaje, cijena za jedinicu mjere (ako je primjenjivo), barkod (ako je primjenjivo), EAN (ako je posebno zabilježen), bazna cijena.
- **Usluge (5 stupaca):** naziv, maloprodajna cijena, posebni oblik prodaje, naziv posebnog oblika prodaje, bazna cijena.
- Datoteke se pišu u UTF-8 bez BOM-a, razdvojene točkom-zarezom; XML s odgovarajućim elementima.
- **Neto količina i EAN ostaju prazni kada nisu primjenjivi ili nisu potvrđeni** – ne izvode se iz veličine remena ili interne šifre COV.
- U nazivima verzioniranih datoteka uključeni su MBO Covart obrta, vrsta/adresa/oznaka prodajnog mjesta, oznaka robe/usluge, broj pohrane i lokalno vrijeme objave.

## Dvije vrste poveznica

1. `current/98946498_*_AKTUALNI.csv|xml` – stalne URL adrese; njihov se sadržaj ažurira kad se cijene promijene.
2. `current/98946498_*_<broj_pohrane>_<GGGGMMDD_SSMM>.csv|xml` – pojedinačne datoteke s propisanim podacima u nazivu. Svaka objava istodobno ima arhivsku kopiju u `archive/YYYY-MM-DD/`.

**Važno:** stalni alias nema vlastiti vremenski broj u nazivu. Propisani puni naziv ima verzionirana datoteka, a alias zadovoljava tehnički zahtjev stabilne URL adrese. Takvu kombinaciju vrijedi dodatno potvrditi s pravnim savjetnikom ili nadležnim tijelom – ona nije formalno mišljenje o potpunoj usklađenosti.

## Raspored

Primarna provjera 07:15 i rezerva 07:35 po lokalnom vremenu, dodatna provjera 10:50. Ako cijene mijenjate kasnije, potrebno je prije promjene koordinirati novu objavu (pravilo najkasnije do 11:00 na dan promjene). Izmjene se objavljuju samo kada su podaci promijenjeni; ranija arhiva se ne briše.

## Prodajna mjesta i Shopify

Oznake `WEB01`, `PPP01`, `USL01` naslijeđene su iz prethodnog sustava. Njihovu točnost prema službenom razvrstavanju prodajnih mjesta treba potvrditi.

GitHub objava sama po sebi **ne mijenja automatski datoteke u Shopify temi**. Javni cjenik treba povezati sa stalnim URL adresama iz ovog repozitorija i uskladiti zastarjele datoteke koje tema trenutačno sadrži.
