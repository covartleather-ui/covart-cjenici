# COVART — tehnička revizija cjenika NN 132/2026

**Datum provjere:** 18. 11. 2026. (Europe/Zagreb)  
**Obuhvat:** Shopify, GitHub `covartleather-ui/covart-cjenici`, datoteke, URL preusmjeravanja, regresijski testovi i jutarnje automatizacije.  
**Vrsta zahvata:** samo dokumentacija; bez promjene prodajnih cijena, baznih cijena, generatora, workflowa, proizvoda i povijesnih arhiva.

## Zaključak

Nije potvrđen aktualni nesklad između objave GitHub `000041`, aktualnog Shopify cjenika i šest pripadajućih datoteka. Traženje verzije `000038` ili `000029` u vanjskom indeksiranom rezultatu ne dokazuje zastarjeli Shopify: izvori izravno pročitani iz Shopify Admin API-ja potvrđuju aktualnu `000041`. Nisu izvedeni nepotrebni tehnički popravci.

**Nedovršene dokazne provjere:** anonimni HTTP GET svih javnih datoteka nije mogao biti izvršen alatima ove sesije; podaci o povijesnoj stvarnoj najnižoj cijeni 30 dana prije početka pojedinih osam sniženja nisu neovisno dokazani; nema provedenog namjernog testa kvara Shopify sinkronizacije ni jamstva izvršavanja prije zakonskog roka kada GitHub Actions kasni. Status `READY` i ispravno preusmjeravanje nisu zamjena za anonimni GET.

## 1. Verzije, identifikatori i Shopify

- Matični broj obrta: `98946498`.
- Manifest `current/manifest.json`: `storage_sequence=000041`, `published_at=2026-11-17T09:48:45+01:00`, `format_version=NN132_2026`.
- Shopify stranica `https://covart-shop.com/pages/cjenik`: objava `000041`, 17.11.2026. 09:48. Shopify `updatedAt=2026-11-18T06:51:27Z` (07:51 Zagreb); stranica bilježi istu zadnju sinkronizaciju.
- Shopify Files: svih šest verzioniranih datoteka `000041` ima status `READY`. Njihove veličine u bajtovima identične su duljinama odgovarajućih GitHub izvora: webshop CSV 11687, XML 57015; radionica CSV 13668, XML 67519; usluge CSV 2081, XML 12105.
- Šest datoteka s imenima `_AKTUALNI` u GitHub `current/` sadržajem su **identične** odgovarajućim verzioniranim datotekama. `_AKTUALNI` služi kao stabilni alias; kanonski arhivski i aktualni cilj ima propisanu oznaku, broj pohrane i datum/vrijeme.

## 2. Javni URL i arhiva

- U Shopify stranici `/pages/cjenik` postoji **54 poveznice** pod `https://covart-shop.com/cjenici/`: 6 aktualnih verzioniranih, 6 stabilnih aktualnih i 42 arhivske.
- **54/54** poveznica imaju Shopify `UrlRedirect` s ciljnom datotekom u `cdn.shopify.com`, a ciljna `GenericFile` datoteka ima `fileStatus=READY`.
- Arhive objava `000034`–`000041` imaju po šest datoteka sa statusom `READY`; izvorne datoteke `000001`–`000033` nisu vraćane na Shopify sukladno ranijem vlasnikovu nalogu (ostaju u GitHub arhivi).
- Šest datoteka iz GitHub `current/` za `000041` byte-for-byte je identično kopijama u `archive/2026-11-17/` (usporedba dohvaćenog sadržaja).
- Mrežna stranica `/pages/cjenik` ostaje na istoj adresi pri ažuriranju, s poveznicama na propisno imenovane verzionirane datoteke; `/cjenici/aktualni/` je dodatni trajni alias. Ovo je konzistentno s razlikom između stalne URL adrese objave i izmjenjivih naziva datoteka iz članka 6. Pravilnika.
- **Ograničenje:** anonimni vanjski HTTP GET i status HTTP 200 nisu mogli biti neovisno provjereni iz ovog alata; validirana je administratorska konfiguracija preusmjeravanja, READY status i naziv ciljne datoteke.

## 3. CSV/XML, cijene i Shopify izvori

- Webshop: 111 aktivnih varijanti, 111 jedinstvenih SKU oznaka, bez odstupanja između Shopify trenutačne cijene/bazne cijene i GitHub CSV-a; podaci o posebnim oblicima prodaje također odgovaraju.
- Radionica/sajam: 132 SKU oznake, svih 132 jedinstveno; uključuje 111 webshop varijanti + 21 aktivan Shopify metaobjekt `covart_workshop_product`. **21/21** metaobjekt podudara se s CSV-om u aktualnoj i baznoj cijeni i oznaci posebne prodaje.
- Usluge i dostava: **44/44** aktivnih Shopify metaobjekata `covart_service_price` podudaraju se s CSV-om (aktualna, bazna i posebna prodaja).
- Svih šest CSV/XML datoteka sadrži očekivani broj zapisa 111/132/44. CSV: UTF-8 bez BOM-a, `;` razdjelnik, CRLF retci, propisani redoslijed polja, potpuna polja i valjane novčane vrijednosti. XML: UTF-8 deklaracija, odgovarajući atributi obrta i objave, parni otvarajući/zatvarajući zapisi.
- CSV i XML za pojedinu kategoriju međusobno se podudaraju po **svakoj vrijednosti svakog zapisa**: **287/287 zapisa**, bez odstupanja.
- Podaci o povijesnim baznim cijenama ne rekonstruiraju se niti automatski izmišljaju; Shopify metafieldi su izvor. Međutim, bez neovisne cjenovne povijesti nije moguće dokazati sve izvorne datume i cijene. Osam sniženih Shopify varijanti ima polje `custom.lowest_30_day_price`; valja neovisno potvrditi vrijednost koja je vrijedila 30 dana **prije početka sniženja**, a ne samo današnju vrijednost tog polja. Cijene nisu dirane.

## 4. Testovi, raspored, scenariji i upozorenja

- GitHub Actions `publish-price-lists.yml`, zadnje pregledano izvršenje: **44369770078**, 18.11.2026. u 18:26 UTC, status `success`. Regresijski testovi: **14 tests, OK**.
- Pokrivenost testova: novo objavljivanje pri promjeni podataka (uključujući isti dan), neobjavljivanje bez promjene i pri ručnoj/push provjeri, idempotentnost, neprihvaćanje ponovljenih SKU i nedokumentiranih baznih cijena, redoslijed stupaca, UTF-8/CSV i očuvanje povijesne arhive.
- Stvarno zadnje izvršenje ispisalo je `No relevant Shopify price-list changes; publication skipped.` i `No publication changes to commit.` — nije nastala nepotrebna objava `000042`.
- GitHub Actions ima jutarnje rasporede (uz provjeru ljetnog/zimskog vremena) i naknadni sigurnosni termin; postoje dvije omogućene automatizacije: `Covart cjenici` u 07:50 (sinkronizacija) i `Provjera Covart cjenika` u 08:10 (neovisna provjera), vremenska zona Zagreb. Automatizacije imaju upute prijaviti grešku/nepodudarnost bez lažnog uspjeha.
- **Preostali operativni rizik:** GitHub `schedule` nije strogo vremensko jamstvo. Nije proveden test stvarnog pada Shopify objave ni izvršavanja po novoj promjeni cijena neposredno prije 11:00; ne može se jamčiti rok u svim uvjetima bez boljeg nadzora/okidanja promjene. Nije uvedena nova automatizacija jer nije utvrđen aktualni kvar, a korisnik traži minimalne intervencije.

## 5. Pravna podloga

- [NN 132/2026, 1583 — Pravilnik o isticanju bazne cijene proizvoda](https://narodne-novine.nn.hr/eli/sluzbeni/2026/132/1583): čl. 3.–6. (referentne cijene, iznimke i isticanje).
- [NN 132/2026, 1584 — Pravilnik o načinu objave cjenika proizvoda](https://narodne-novine.nn.hr/eli/sluzbeni/2026/132/1584): čl. 3. (polja, rok 11:00 i arhiva 15 dana), čl. 5. (automatizirani pristup), čl. 6. (CSV/XML, ista URL adresa objave, imenovanje, UTF-8 i separator).
- Audit je tehnička provjera; nije potpuna pravna potvrda povijesnog određivanja cijena, stvarne anonimne HTTP dostupnosti niti fizičkog isticanja baznih cijena na prodajnom mjestu.

## 6. Promjene i odluka

**Funkcionalne datoteke promijenjene: nijedna.** Povijesne arhive, Shopify proizvodi, cijene, teme i pravni tekstovi nisu mijenjani.

**Nova dokumentacija:** `audits/nn132-price-lists-technical-audit-2026-11-18.md`.

**Status:** tehnički podaci i postavke usklađeni; neprovjereni detalji ostaju izričito otvoreni. Ne objavljuj novu verziju cjenika bez stvarne promjene.
