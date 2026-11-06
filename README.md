# BasketballBet

Streamlit εφαρμογή: `app.py`, έκδοση **BASKET-2026-11-06-GREECE3**. Διατηρούνται NBA, EuroLeague και Ελλάδα – Basket League.

## Ελληνική Basket League — 06/11/2026

Για την Ελλάδα προηγείται πλέον το επίσημο πρόγραμμα/αποτελέσματα του [ΕΣΑΚΕ](https://www.esake.gr/el/action/EsakePrograms), με εναλλακτική το Sofascore. Δεν απαιτείται νέο κλειδί. Η επιλογή ημερομηνίας αφορά Europe/Athens· επίλεξε 07/11 ή 08/11 για τους αντίστοιχους αγώνες του Σαββατοκύριακου. Δεν καταχωρίζονται στατικοί αγώνες στον κώδικα.

Η πηγή διαβάζει την πραγματικά επιλεγμένη διοργάνωση/σεζόν, τις ομάδες με τα επίσημα αναγνωριστικά τους και τις δημοσιευμένες ώρες. Ασαφείς ώρες/TBA και άγνωστες σεζόν απορρίπτονται. Η ανάγνωση των επιλογών υποστηρίζει τα HTML defaults (πρώτη επιλογή όταν δεν υπάρχει selected), διαφορετικό id/name του πεδίου και προαιρετικά κλεισίματα option. Αν υπάρχει αρχική κενή επιλογή, η σεζόν γίνεται δεκτή μόνο με μοναδικό επιβεβαιωμένο τίτλο GBL που συμφωνεί με τον κατάλογο. Αν το πρόγραμμα δεν παρέχει επαληθεύσιμη φόρμα, δοκιμάζεται και το επίσημο EsakeResults. Η ζητούμενη σεζόν/φάση εξακολουθεί να ελέγχεται σε κάθε αγωνιστική. Το τρέχον πρόγραμμα επαναχρησιμοποιείται από cache 120s. Για άλλες ημερομηνίες και ιστορικό αναζητούνται οι δημοσιευμένες αγωνιστικές/φάσεις της σεζόν, με περιορισμένη παράλληλη ανάκτηση και cache 600s. Το μοντέλο εξακολουθεί να απαιτεί 10 προηγούμενους ολοκληρωμένους αγώνες ανά ομάδα· ελλείπον ιστορικό παραμένει έλλειψη. Ο ΕΣΑΚΕ παρέχει πρόγραμμα/αποτελέσματα, όχι αποδόσεις στοιχηματικών.

Διορθώθηκε και το φίλτρο Sofascore: αναγνωρίζει το σταθερό αναγνωριστικό της ανδρικής διοργάνωσης 304 και τις ονομασίες `stoiximan-basket-league` / `stoiximan-gbl`, με έλεγχο χώρας, αποκλείοντας άλλες διοργανώσεις όπως το κύπελλο 608.

`python check_greek_basket.py`: ελεγχόμενες HTML σελίδες σύμφωνα με τη δημοσιευμένη δομή του ΕΣΑΚΕ, 5 αγώνες Σαββάτου/2 Κυριακής, ώρες Ελλάδας, σεζόν, αναγνωριστικά, άγνωστη ώρα, archive/result/history, cache/fallback και Streamlit UI. Οι ονομασίες/ώρες του επίσημου προγράμματος 7–8 Νοεμβρίου επιβεβαιώθηκαν μέσω δημόσιας ανάγνωσης. **Η ζωντανή HTTP ανάκτηση του ΕΣΑΚΕ από το περιβάλλον ανάπτυξης αποκλείεται από την πολιτική δικτύου· δεν έχει επιβεβαιωθεί ακόμη από τη φιλοξενούμενη εφαρμογή.** Το Sofascore επιστρέφει HTTP 403 challenge εδώ. Αποτυχίες εμφανίζονται στην «Κατάσταση πηγών», χωρίς παράκαμψη πρόσβασης ή υποθετικά δεδομένα.

Προηγούμενη έκδοση: [backup/before-greece-2026-11-06](https://github.com/mgiobaras/basketballbet/tree/backup/before-greece-2026-11-06).

## Εμφάνιση ιστορικού — 05/11/2026

Λευκό θέμα με πράσινες λεπτομέρειες και διακριτικό σχέδιο γηπέδου μπάσκετ. Τα Κερδισμένα / Χαμένα / Εκκρεμή εμφανίζονται σε μία σειρά και σε μικρή οθόνη. Οι επιστροφές παραμένουν χωριστές και εξαιρούνται από την επιτυχία. Το ιστορικό και το CSV ταξινομούνται κατά έναρξη από παλαιότερη σε νεότερη και, στην ίδια ώρα, κατά μεγαλύτερη αρχική πιθανότητα. Η ώρα εμφανίζεται σε Europe/Athens· οι αρχικές πιθανότητες/εγγραφές δεν αλλάζουν. Η επιλογή αγώνα διατηρείται με το αναγνωριστικό του ακόμη και αν αναδιαταχθεί η πηγή.

Δεν αλλάζουν υπολογισμοί, αποδόσεις, βάση ή Secrets. Πλήρες αντίγραφο προηγούμενης έκδοσης: [backup/before-ui-2026-11-05](https://github.com/mgiobaras/basketballbet/tree/backup/before-ui-2026-11-05). Έλεγχοι: `python check_history_ui.py`, `python check_basketball.py`, `python check_pace.py`.

## Προαιρετικό μοντέλο ρυθμού και αποτελεσματικότητας — 03/11/2026

Στο «Μοντέλο υπολογισμού» παραμένει προεπιλεγμένο το κλασικό μοντέλο. Η επιλογή «Ρυθμός & αποτελεσματικότητα — πειραματικό» προσθέτει αναλυτικά ομαδικά στατιστικά για NBA και Ευρωλίγκα. Δεν έχει αποδειχθεί βελτίωση ακρίβειας ή κερδοφορίας.

- Χρησιμοποιεί ακριβώς τους ίδιους τελευταίους 10 ολοκληρωμένους αγώνες ανά ομάδα, στην ίδια διοργάνωση και πριν από την έναρξη του επιλεγμένου αγώνα. Αν λείπει κάποιο αναλυτικό box score, δεν αντικαθιστά τον αγώνα με παλαιότερο και δεν κατασκευάζει τιμές. Μπορείς να επιλέξεις το κλασικό μοντέλο.
- Εκτίμηση κατοχών ανά ομάδα: `FGA - ORB + TOV + 0.44 × FTA`. Οι κατοχές του αγώνα είναι ο μέσος όρος των δύο ομάδων. Πρόκειται για προσέγγιση από το box score, όχι καταμέτρηση κάθε πραγματικής κατοχής.
- Επίθεση/άμυνα: πόντοι υπέρ/κατά ανά 100 εκτιμώμενες κατοχές. Ρυθμός: κατοχές ανά 48 λεπτά στο NBA ή 40 στην Ευρωλίγκα, προσαρμοσμένες στην πραγματική διάρκεια μαζί με τις παρατάσεις. Ίδια βάρη ημιζωής 90 ημερών με το κλασικό μοντέλο.
- Οι αναμενόμενες συνολικές κατοχές είναι ο μέσος όρος των ιστορικών κατοχών ανά αγώνα των δύο ομάδων, μαζί με την ιστορική επίδραση παρατάσεων. Πόντοι γηπεδούχου = αναμενόμενες κατοχές × μέσος όρος δικής του επίθεσης και αντίπαλης άμυνας / 100, αντίστοιχα για φιλοξενούμενο. Η Normal διακύμανση παραμένει η εμπειρική διακύμανση πόντων του κλασικού μοντέλου· η νέα προσέγγιση δεν έχει βαθμονομηθεί/backtested. Δεν προσαρμόζεται στη συνολική δυναμικότητα των αντιπάλων.
- Η έκδοση μοντέλου, οι αγώνες, τα συνοπτικά αναλυτικά στατιστικά και τα URL πηγών αποθηκεύονται μαζί με κάθε νέα επιλογή. Οι προηγούμενες επιλογές και οι αρχικές πιθανότητες παραμένουν αμετάβλητες. Το ιστορικό εμφανίζει και την έκδοση μοντέλου.

**Κόστος δεδομένων:** η [Opta/Stats Perform](https://www.statsperform.com/faqs/stats-perform-faqs-pricing-licensing/) παρέχει εξατομικευμένη εμπορική αδειοδότηση, χωρίς δημοσιευμένο μόνιμο δωρεάν πρόγραμμα API. Δεν ενεργοποιήθηκε τέτοια υπηρεσία. Χρησιμοποιούνται δημόσια προσβάσιμα EuroLeague `…/seasons/E{year}/games/{gameCode}/stats` και ESPN NBA `…/summary?event={id}`: επαληθεύτηκαν με HTTP 200 χωρίς κλειδί ή χρέωση ανά αίτημα. Δεν αποτελούν συμβατική εγγύηση μόνιμης δωρεάν παροχής. Δεν χρειάζονται νέα Secrets, συνδρομή ή βιβλιοθήκη. Τα επιτυχημένα συνοπτικά box scores αποθηκεύονται στην cache για 7 ημέρες· μη έγκυρες απαντήσεις απορρίπτονται.

**Επιστροφή στην προηγούμενη έκδοση:** πλήρες αντίγραφο του προηγούμενου `main` πριν τις αλλαγές διατηρείται στο [backup/before-pace-2026-11-03](https://github.com/mgiobaras/basketballbet/tree/backup/before-pace-2026-11-03), commit `165ab494a7beb4d193142ff778212118a6b7a870`. Η επιλογή «Κλασικό» διατηρεί και μέσα στην εφαρμογή τον προηγούμενο υπολογισμό. Για πλήρη επαναφορά στο Streamlit μπορεί να επιλεγεί αυτό το backup branch με main file `app.py`.

Έλεγχος νέου μοντέλου: `python check_pace.py` (πραγματικές μειωμένες απαντήσεις NBA/EuroLeague, αριθμητικός έλεγχος, παρατάσεις, ταυτότητα/cache, αποκλεισμός μελλοντικών, αποθήκευση και Streamlit UI). Είναι λειτουργικός έλεγχος, όχι απόδειξη προβλεπτικής ακρίβειας.

## Αυτόματη εισαγωγή

Δεν επιλέγεις πηγή. Η εφαρμογή δοκιμάζει διαδοχικά τις συνδεδεμένες πηγές όταν λείπουν αγώνες, ιστορικό, αγορές ή αποτελέσματα:

- NBA: ESPN → Sofascore.
- EuroLeague: επίσημο EuroLeague API για αγώνες/σκορ· αποδόσεις από διαθέσιμες δημόσιες πηγές και αυτόματη εναλλακτική Paf, εφόσον επιστρέφουν στοιχεία.
- Ελλάδα: επίσημο πρόγραμμα/αποτελέσματα ΕΣΑΚΕ → Sofascore. Αν αποτύχουν, η εφαρμογή δείχνει την αποτυχία χωρίς στατικούς αγώνες ή μέσους όρους.

Οι διαφορετικές πηγές συνδέονται μόνο με ίδια διοργάνωση, γηπεδούχο/φιλοξενούμενο, ακριβή ονόματα/ρητά aliases και πραγματική ώρα έναρξης. Δεν γίνεται fuzzy αντιστοίχιση. Σκορ που διαφωνούν ή αμφίβολη ταυτότητα σταματούν τον υπολογισμό.

Οι αποδόσεις και τα **Over/Under lines και signed handicaps** εισάγονται μαζί από την ίδια καταγραφή. Κάθε αγορά διατηρεί το δικό της line, εταιρεία/δημοσιευμένο ID παρόχου, πηγή, event, URL και πραγματική ώρα λήψης. Τα θετικά/αρνητικά handicap αφορούν τη συγκεκριμένη πλευρά. Δεν αντιγράφεται η ίδια προσημασμένη γραμμή στην άλλη ομάδα.

Οι αγορές αφορούν ολόκληρο τον αγώνα **μαζί με παράταση**. Αγορές περιόδου ή ασαφούς scope δεν εισάγονται. Το ESPN μπορεί να δίνει `current` ή μόνο δημοσιευμένο `close` snapshot: η εφαρμογή τα επισημαίνει χωριστά, δεν τα παρουσιάζει ως εγγυημένες ζωντανές/εκτελέσιμες τιμές και δεν χρησιμοποιεί opening τιμές ως current. Από το Sofascore γίνονται δεκτές μόνο αγορές με ρητή ένδειξη παράτασης. Αν δεν δίνεται όνομα εταιρείας, εμφανίζεται το πραγματικό ID παρόχου ως μη δηλωμένη εταιρεία, χωρίς επινόηση ονόματος.

Ελλείψεις μένουν κενές. Δεν υπάρχει προεπιλεγμένη απόδοση1,90, line165,5 ή handicap−3,5. Υπάρχει προαιρετική χειροκίνητη καταχώριση πραγματικών τιμών με υποχρεωτική εταιρεία.

## Πρόβλεψη

Χρησιμοποιούνται μόνο οι **10 τελευταίοι πραγματικοί ολοκληρωμένοι αγώνες ανά ομάδα στην ίδια διοργάνωση**, πριν από τον επιλεγμένο αγώνα. Όταν λείπει το δείγμα, η εφαρμογή δείχνει τους πραγματικούς διαθέσιμους αριθμούς και απέχει.

Σταθμισμένοι πόντοι υπέρ/κατά με ημιζωή90 ημερών, μέσος της επίθεσης της ομάδας και της άμυνας του αντιπάλου. Οι διακυμάνσεις προέρχονται από τις ίδιες παρατηρήσεις. Το πειραματικό μοντέλο χρησιμοποιεί ανεξάρτητη Normal προσέγγιση των πόντων, με διόρθωση ακέραιων σκορ και χωριστή πιθανότητα επιστροφής σε ακέραια γραμμή. Δεν μεταφέρεται η Poisson ποδοσφαίρου σε πόντους μπάσκετ. Δεν υπάρχουν υποθετικοί μέσοι όροι ομάδων, σταθερό πλεονέκτημα έδρας, συντελεστές ξεκούρασης, τεχνητά κατώφλια σκορ/διακύμανσης ή Kelly.

Οι **απουσίες καταχωρίζονται χειροκίνητα**: βασικός−1, αναπληρωματικός−0,5. Ο δείκτης αποθηκεύεται μόνο, χωρίς αυθαίρετη μεταβολή πιθανοτήτων. Κενή καταχώριση σημαίνει άγνωστο.

Το μοντέλο δεν έχει αξιολογηθεί σε ιστορικό ανεξάρτητο backtest. **Το70%, η βαθμονόμηση και η κερδοφορία δεν έχουν επιβεβαιωθεί.** Τα σκορ είναι προσέγγιση μοντέλου, όχι πραγματικά μελλοντικά αποτελέσματα.

## Ιστορικό και αποτελέσματα

- Ίσο ποντάρισμα **1 μονάδας**, ελάχιστη απόδοση **1,50**.
- Καμία νέα αποθήκευση μετά την έναρξη. Λήψη παλιότερη από5 λεπτά χρειάζεται ανανέωση.
- Διπλή αποθήκευση ίδιας αγοράς/αγώνα δεν αλλάζει την αρχική απόδοση ή γραμμή.
- Αυτόματη ενημέρωση κατά τη χρήση της εφαρμογής και κουμπί ανανέωσης. Δεν είναι scheduler όταν η εφαρμογή είναι κλειστή.
- Επιβεβαιωμένο τελικό σκορ με παράταση. Σε ισοπαλία στην ακέραια γραμμή επιστρέφεται η μονάδα, χωρίς κέρδος/ζημιά. Άγνωστα, αναβολές και μη ολοκληρωμένοι αγώνες μένουν εκκρεμή.
- Επιτυχία υπολογίζεται από κερδισμένα/χαμένα, χωρίς pending ή επιστροφές. ROI/κέρδος από εκκαθαρισμένες επιλογές, με επιστροφή0 κέρδους. Το δείγμα εμφανίζεται χωριστά.
- Εξαγωγές CSV/JSON. Το παλιό `basketball_predictions_history.csv` διατηρείται ανέπαφο, με ξεχωριστό αντίγραφο στη βάση· δεν μετατρέπεται σε επαληθευμένα νέα στοιχήματα. Το αρχικό πρόγραμμα βρίσκεται στο `baseline/app_original.py`.

## Τοπική εκκίνηση

Python3.11+:

```sh
python -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m streamlit run app.py
```

Στα Windows: `.venv\Scripts\python -m pip install -r requirements.txt` και `.venv\Scripts\python -m streamlit run app.py`.

Χωρίς cloud ρυθμίσεις χρησιμοποιείται SQLite `data/basketball.sqlite3`. Το `BET_DB_PATH` επιλέγει άλλη διαδρομή μόνιμου δίσκου. Στο Streamlit Cloud η τοπική αποθήκευση μπορεί να χαθεί σε επανεκκίνηση.

## Μόνιμη αποθήκευση Supabase και προσωπική πρόσβαση

Για την αντίστοιχη μόνιμη αποθήκευση του ποδοσφαίρου:

1. Εκτέλεσε το `database/supabase_setup.sql` στον SQL Editor του Supabase. Είναι επαναλήψιμο και δημιουργεί **χωριστούς basketball πίνακες**· μπορεί να χρησιμοποιηθεί το ίδιο Supabase project χωρίς αλλαγή των football πινάκων.
2. Στα **Secrets της υπάρχουσας basketball Streamlit εφαρμογής**, βάλε τα παρακάτω με τις δικές σου τιμές, ποτέ στη συνομιλία ή στο GitHub:

```toml
REQUIRE_REMOTE_DB = true
SUPABASE_URL = "https://YOUR_PROJECT_REF.supabase.co"
SUPABASE_SERVICE_ROLE_KEY = "YOUR_SERVER_SECRET_KEY"
APP_PASSWORD = "YOUR_OWN_PRIVATE_APP_PASSWORD"
```

Το server key μπορεί να είναι `sb_secret_…` ή legacy `service_role`, ποτέ anon/publishable. Αποτυχία remote σύνδεσης σταματά την εφαρμογή, χωρίς σιωπηλή τοπική αποθήκευση. Το login προηγείται οποιασδήποτε πρόσβασης στη μόνιμη βάση.

Η υπάρχουσα εγκατάσταση πρέπει να χρησιμοποιεί repository `mgiobaras/basketballbet`, branch `main`, main file `app.py`. Δεν χρειάζεται νέο app ή πληρωμένο odds API.

## Έλεγχοι και όρια επαλήθευσης

```sh
python check_basketball.py
python check_cloud_storage.py
```

Ο πρώτος ελέγχει με ελεγχόμενα δεδομένα την ταυτότητα αγώνα, τις γραμμές/αποδόσεις, fallback, τελευταίους10, αποκλεισμό μελλοντικών, refunds, SQLite, immutable quotes, παλιό ιστορικό και UI. Ο δεύτερος χρειάζεται Docker και ελέγχει πραγματικό PostgreSQL/PostgREST: private tables, διπλές καταχωρίσεις, ακέραιες γραμμές, cache και διατήρηση μετά από restart. Αυτά είναι λειτουργικοί έλεγχοι, όχι backtest επιτυχίας.

Στο περιβάλλον ανάπτυξης επιβεβαιώθηκε live NBA ESPN: αγώνες, έξι αγορές μαζί με τις αντίστοιχες γραμμές και 10 πραγματικοί αγώνες ανά ομάδα. Στις 03/11/2026 επαληθεύτηκε και το νέο μοντέλο με πραγματικά box scores: Ρεάλ–Παναθηναϊκός 04/11 (20 διαφορετικοί προηγούμενοι αγώνες) και Orlando–Boston 01/11 (19 διαφορετικοί προηγούμενοι αγώνες, επειδή ένας ήταν κοινός). Κάθε ομάδα χρησιμοποίησε τους δικούς της 10 πιο πρόσφατους αγώνες πριν το αντίστοιχο kickoff, χωρίς πρόσβαση σε μελλοντικά σκορ. Το Sofascore εξακολουθεί να επιστρέφει HTTP 403 από αυτό το περιβάλλον. Η πρόσβαση από τη hosted Streamlit εγκατάσταση χρειάζεται επιβεβαίωση εκεί. Καμία πηγή δεν εγγυάται κάθε αγώνα/αγορά.


### Ιστορικό ανά διοργάνωση

Το αναπτυσσόμενο μενού διοργανώσεων στο ιστορικό φιλτράρει τον πίνακα και τα στατιστικά κερδισμένων, χαμένων, εκκρεμών, επιτυχίας, κέρδους και ROI. Το «Σύνολο» εμφανίζει όλες τις διοργανώσεις. Στο μπάσκετ οι επιστροφές εμφανίζονται χωριστά και δεν θεωρούνται χαμένα. Η «Αρχική πιθανότητα μοντέλου» είναι το ποσοστό που αποθηκεύτηκε μαζί με την επιλογή, χωρίς επανυπολογισμό. Δεν χρειάζεται αλλαγή βάσης ή Secrets.


### Προαιρετική πηγή αποδόσεων: The Odds API

Αν το Sofascore επιστρέφει HTTP 403 ή οι δημόσιες πηγές δεν καλύπτουν τις αγορές,
η εφαρμογή μπορεί να συμπληρώνει τις ελλείπουσες αποδόσεις NBA/EuroLeague μέσω
του [The Odds API](https://the-odds-api.com/). Χρειάζεται δικό σου κλειδί.
Η σύνδεση παραμένει ανενεργή χωρίς αυτό.

1. Δημιούργησε δωρεάν κλειδί στο **the-odds-api.com** (με παύλες).
2. Στα Streamlit **Manage app → Settings → Secrets** πρόσθεσε μόνο τη νέα γραμμή,
   διατηρώντας τα υπάρχοντα Secrets:
   ```toml
   ODDS_API_KEY = "ΤΟ_ΔΙΚΟ_ΣΟΥ_ΚΛΕΙΔΙ"
   ```
3. Αποθήκευσε, κάνε Reboot αν χρειάζεται και πάτησε «Ανανέωση αποδόσεων».

Το δωρεάν πρόγραμμα δηλώνει 500 credits/μήνα κατά τον έλεγχο στις 2026-11-03.
Ένα αίτημα για νικητή, handicap και σύνολο πόντων στην περιοχή eu κοστίζει έως
3 credits. Το ίδιο feed επαναχρησιμοποιείται για 120 δευτερόλεπτα μεταξύ αγώνων
της ίδιας διοργάνωσης. Η συχνή ανανέωση καταναλώνει το δωρεάν όριο.
Δεν χρειάζεται πληρωμένη συνδρομή για την αρχική δοκιμή. Η κάλυψη συγκεκριμένου
αγώνα, αγοράς ή εταιρείας εξαρτάται από τα δεδομένα που επιστρέφονται.

Η αντιστοίχιση ελέγχει διοργάνωση, ακριβή έναρξη, γηπεδούχο και φιλοξενούμενο.
Γίνονται δεκτές μόνο οι κύριες αγορές h2h/spreads/totals πλήρους αγώνα.
Κάθε επιλογή διατηρεί την πραγματική εταιρεία, τη γραμμή, την τιμή, το source event
και τις ώρες λήψης/δημοσίευσης. Το κλειδί δεν γράφεται στις αποθηκευμένες επιλογές,
στα URLs προέλευσης ή στα μηνύματα σφαλμάτων. Μην το βάζεις στο GitHub ή στο chat.

Έλεγχοι χωρίς πραγματικό κλειδί: `python check_odds_api.py`,
`python check_euro_odds.py` και `python check_basketball.py`.
Η live πρόσβαση και οι τιμές του δικού σου λογαριασμού χρειάζονται επιβεβαίωση
μετά την προσθήκη κλειδιού. Τεκμηρίωση:
[κάλυψη αθλημάτων](https://the-odds-api.com/sports-odds-data/sports-apis.html),
[API και χρέωση credits](https://the-odds-api.com/liveapi/guides/v4/).

### Αυτόματη εναλλακτική Paf χωρίς κλειδί

Η έκδοση `BASKET-EURO-ODDS3` προσθέτει δημόσια τροφοδοσία Paf/Kambi ως
εναλλακτική για αποδόσεις Ευρωλίγκας, πριν από το προαιρετικό The Odds API.
Δεν απαιτείται λογαριασμός, νέο Secret ή συνδρομή για την ενεργοποίηση του κώδικα.
Δεν χρησιμοποιούνται σταθερές αρχικές αποδόσεις ως αυτόματες τιμές.

Ελέγχονται διοργάνωση, γηπεδούχος, φιλοξενούμενος, ώρα και κατάσταση αγώνα.
Γίνονται δεκτές μόνο ανοιχτές κύριες αγορές με ρητή ένδειξη παράτασης.
Οι γραμμές και οι αποδόσεις μετατρέπονται από τις χιλιοστές μονάδες της πηγής
και αποθηκεύονται μαζί με εταιρεία, URL και αναγνωριστικό του πραγματικού αγώνα.
Η λίστα αγώνων επαναχρησιμοποιείται από την cache ώστε να αποφεύγονται περιττά αιτήματα.

Σε HTTP 403 ή άλλη άρνηση δεν γίνεται παράκαμψη, αλλαγή proxy ή πλαστογράφηση
τοποθεσίας. Το μήνυμα εμφανίζεται στην «Κατάσταση πηγών». Η πηγή μπορεί να
μην καλύπτει κάθε αγώνα ή να αρνείται πρόσβαση από συγκεκριμένο server.
Έλεγχος με καταγεγραμμένα δεδομένα πηγής: `python check_paf_odds.py`.
Η ζωντανή πρόσβαση από την εγκατάσταση Streamlit χρειάζεται επιβεβαίωση εκεί.

### Private analysis log

Every successful Calculate records a separate immutable snapshot of the selected
fixture, all market probabilities, actual quotes/lines where available, missing
values, absences, selected model version and the observations used. No additional
sports-data requests are made just for logging. Games the user never calculates
are not logged. Basketball markets without a real total/handicap line have null
probability; no line or price is invented. Only the model actually calculated is
recorded, including its version when experimental pace mode is selected.

There is no new log table or control in the app UI. Selected-bet history, its
JSON/CSV exports, results and ROI remain unchanged. Logs are not automatically
converted to bets and do not retrain the model. Later evaluation must join
verified final scores and choose one fixed pregame snapshot per fixture, market
and model version; independent recalculations must not inflate the sample.
Analyses captured at/after kickoff or outside NS are marked ineligible for
pregame evaluation. Old history is not backfilled as new forecasts.

For an existing Supabase installation run `database/enable_prediction_logging.sql`
in the SQL Editor once per project (once total if both apps share the project).
New installations can use the complete `database/supabase_setup.sql`. The
migration only adds a private table and a private export function, can be
repeated, and never modifies existing bet/history tables. Only the server's
service_role can read/insert log records; anon/authenticated cannot read them,
and the REST service role cannot update/delete these snapshots.

For an owner export use the Supabase SQL Editor:

```sql
select public.app_list_prediction_logs('football');
-- Or: select public.app_list_prediction_logs('basketball');
```

The server-side store also provides `list_predictions()` for a full JSON export,
independent of the selected-bet export and without the REST row limit.

A failed write shows a warning and retries the same snapshot ID on later reruns
in the same open browser session. Calculations and explicit selected-bet saves
remain usable. A pending snapshot is only in session memory until the database
confirms it; closing/restarting that session before recovery can lose it. There
is no silent temporary-disk fallback for cloud storage. Local SQLite is for local
use and is not durable across Streamlit Cloud restarts.

### ESAKE response diagnostics

The hosted application reported a page containing only the `series` selector,
with no season/championship options or h1–h4 titles. The GREECE2 parser therefore
still rejects it correctly rather than guessing a season. The exact returned
markup is needed before changing season/phase extraction again.

On a failed official catalogue lookup, the Greek league's «Κατάσταση πηγών» now
offers «Λήψη διαγνωστικών ΕΣΑΚΕ» (`esake_diagnostics.json`). It contains only the
public EsakePrograms/EsakeResults response body, source URL, receipt time and
parser error. No app settings, HTTP request/response headers, credentials or
selected-bet history are included. Captures remain in the adapter's memory;
they are not published or written to betting history or Supabase. Each body is
bounded to 2 million characters and explicitly marks truncation. Downloading
allows the owner to provide the actual HTML returned to Streamlit for review.
The GREECE3 fix below was verified against the owner-provided responses; the diagnostic download remains available on subsequent catalogue failures.

### GREECE3: verified against the actual Streamlit responses

The owner supplied `esake_diagnostics.json`, captured on 2026-11-06. ESAKE's
championship, phase and team selectors open with `<select ... />`, followed by
normal options and `</select>`. Python HTMLParser's default start/end callback
closed those selectors immediately, dropping their options. The parser now
keeps non-void select/option elements open, matching browser HTML behavior.
Season/phase/fixture identity checks remain in place.

The actual EsakeResults response also publishes its 26 round choices in button
navigation and JavaScript, while its raw series select contains only a blank
option. The adapter reads the explicit series values from the navigation
buttons without executing JavaScript and sends the source's two-digit round
format. Catalogue/season cache namespaces are v3.

`python check_greek_basket.py` covers malformed select openings and round
navigation alongside the earlier source/UI checks. To replay the full owner
capture locally, without network calls or credentials, run:

```sh
python check_esake_capture.py /path/to/esake_diagnostics.json
```

The actual capture passed: 2026/27 season and regular phase; five 07/11 and two
08/11 fixtures with correct Athens times, home/away and official IDs; seven
completed results with exact scores; all 26 round navigation values; rejection
of a response from the wrong round; and both date-specific Streamlit fixture
lists. Basketball data/model/storage/UI checks also passed. The uploaded JSON
and full HTML are kept outside the repository. This is replay of real hosted
responses, not a new live HTTP test from this development environment or proof
that the live provider will never change its output.
