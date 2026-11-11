# BasketballBet

## CLASSIC1 — επαναφορά κλασικού μοντέλου (11/11/2026)

Ενεργή έκδοση **BASKET-2026-11-11-CLASSIC1**. Ο χρήστης ζήτησε άμεση επαναφορά του κλασικού υπολογισμού. Η εφαρμογή χρησιμοποιεί αποκλειστικά τους πραγματικούς πρόσφατους πόντους υπέρ/κατά, βάρη ημιζωής 90 ημερών και την αρχική ενιαία διακύμανση. Δεν καλούνται οι προσαρμογές κατοχών, total/margin uncertainty ή το πειραματικό NBA. Η επιλογή πειραματικού μοντέλου αφαιρέθηκε και παλιά αποτελέσματα συνεδρίας δεν χρησιμοποιούνται ως νέος κλασικός υπολογισμός.

Παραμένει το ήδη ζητημένο έως 10 πρόσφατων αγώνων: με λιγότερους χρησιμοποιούνται οι διαθέσιμοι και εμφανίζεται το πλήθος, ώστε να συνεχίσει η ελληνική Basket League. Με πλήρες 10/10 οι αριθμητικοί τύποι και πιθανότητες συμφωνούν με το αρχικό κλασικό μοντέλο. Οι νέες εγγραφές φέρουν `basket-classic-restored-v1`. Οι παλιές πιθανότητες, επιλογές, γραμμές, τιμές και εκδόσεις παραμένουν ανέπαφες.

Διατηρούνται οι δημόσιες πηγές δεδομένων/αποδόσεων, οι διορθώσεις ΕΣΑΚΕ/Paf/ονομάτων, οι κάρτες, η μόνιμη αποθήκευση, η ενημέρωση αποτελεσμάτων και η πλήρης ιδιωτική καταγραφή. Η ενότητα κύριων προτάσεων χρησιμοποιεί πάλι την κοινή πολιτική 70%/απόδοση ≥1,50/EV ≥3%, χωρίς το ειδικό μπλοκάρισμα του πειράματος NBA1. Η ιστορική δοκιμή παραμένει διαθέσιμη ως έρευνα και η επαναφορά δεν αποδεικνύει μελλοντική επιτυχία ή κερδοφορία.

Πλήρες αντίγραφο πριν την επαναφορά: [backup/before-classic-restore-2026-11-11](https://github.com/mgiobaras/basketballbet/tree/backup/before-classic-restore-2026-11-11). Δεν απαιτούνται Secrets ή SQL. Έλεγχος ενεργής εφαρμογής: `python check_classic_restore.py`, `python check_basketball.py`, `python check_available_history.py`, `python check_history_ui.py`. Οι παρακάτω ενότητες περιγράφουν παλαιότερες εκδόσεις· οι πειραματικές προσαρμογές δεν είναι ενεργές στην CLASSIC1.

## NBA1 — 2025–2026 experiment (αρχειοθετημένη λειτουργία)

New optional opponent/home-adjusted NBA candidate with empirical residual calibration. It failed the historical recommendation gate and remains experimental, with classic still the default. Selecting the candidate records both variants on identical prices and input games. NBA primary tips are disabled unless a model passes the historical gate; calculations and manual choices remain available. No owner history is rewritten. See [historical results and reproduction](reports/NBA_2025_26_RESULTS.md).


## RECOMMEND1 — διαχωρισμός υπολογισμών και προτάσεων (08/11/2026)

Υπάρχουν πλέον χωριστές ενότητες **Προτάσεις μοντέλου — υπό αξιολόγηση** και **Όλοι οι υπολογισμοί**. Παραμένει δυνατή η αποθήκευση άλλης διαθέσιμης αγοράς ως προσωπική επιλογή.

Η πρώτη πολιτική προτάσεων έχει σταθερή έκδοση: πιθανότητα τουλάχιστον 70%, απόδοση τουλάχιστον 1,50, εκτιμώμενο EV τουλάχιστον 3%, πρόσφατη καταγραφή απόδοσης με εταιρεία και έγκυρη γραμμή, πριν από την έναρξη. Από τις κατάλληλες αγορές επιλέγεται η υψηλότερη πιθανότητα, έπειτα το EV και σταθερή σειρά ως ισοβαθμία. Υπάρχει έως μία τρέχουσα κύρια πρόταση ανά αγώνα. Στο μπάσκετ το όριο πιθανότητας αφορά εκβάσεις χωρίς επιστροφή. Το φίλτρο δεν αποδεικνύει πραγματική επιτυχία 70%.

Κάθε νέος υπολογισμός ή ουσιαστική αλλαγή απόδοσης/γραμμής/απόφασης καταγράφεται χωριστά από τις αποθηκευμένες επιλογές. Απλές επανεκτελέσεις της οθόνης δεν διπλοκαταγράφονται. Η πλήρης εξαγωγή έχει schema_version=2 και επιπλέον model_recommendations: την πρώτη επιλέξιμη καταγραφή με κύρια πρόταση ανά αγώνα και έκδοση πολιτικής. Οι παλιές καταγραφές δεν χαρακτηρίζονται αναδρομικά ως προτάσεις. Δεν χρειάζεται νέο SQL.

Το ιστορικό επιλογών, οι αρχικές πιθανότητες/αποδόσεις/γραμμές, η αυτόματη ενημέρωση αποτελεσμάτων και οι έως 10 πρόσφατοι αγώνες διατηρούνται. Οι προηγούμενες εκδόσεις φυλάσσονται στο branch `backup/before-recommendations-2026-11-08`.

Η εφαρμογή εκτιμά πλέον χωριστά τη διακύμανση συνολικών πόντων και διαφοράς, από τους ίδιους διαθέσιμους έως 10 αγώνες της συγκεκριμένης διοργάνωσης. Περιλαμβάνονται η παρατηρημένη συνδιακύμανση των σκορ, η διόρθωση του πεπερασμένου σταθμισμένου δείγματος και η αβεβαιότητα εκτίμησης μέσων όρων. Δεν εφαρμόστηκε σταθερή αφαίρεση πόντων ή αυθαίρετο όριο διακύμανσης.

Οι αναμενόμενοι πόντοι, τα αναγνωριστικά/πλήθη των παιχνιδιών εισόδου και η κλασική προεπιλογή παραμένουν ίδια. Η προσαρμογή εφαρμόζεται και στην προαιρετική εκδοχή κατοχών, με διατήρηση των πραγματικών box scores. Όταν δεν μπορεί να εκτιμηθεί διακύμανση —όπως με έναν αγώνα ανά ομάδα ή σταθερά σκορ— εμφανίζονται οι διαθέσιμοι μέσοι όροι χωρίς υποθετική βεβαιότητα 100%. Η Normal προσέγγιση και η νέα προσαρμογή παραμένουν υπό αξιολόγηση. Δεν υποστηρίζονται αυθαίρετες δεκαδικές γραμμές όπως 1,665.


Streamlit εφαρμογή: `app.py`, έκδοση **BASKET-2026-11-08-CARDS1**. Διατηρούνται NBA, EuroLeague και Ελλάδα – Basket League.

### Πλήρες αρχείο για ανάλυση

Η κρυφή καταγραφή αποθηκεύει κάθε υπολογισμό με όλες τις αγορές/πιθανότητες/διαθέσιμες τιμές και τα δεδομένα εισόδου, ανεξάρτητα από τις επιλογές που αποθηκεύτηκαν. Περιλαμβάνει τους αγώνες που υπολογίστηκαν στην εφαρμογή, όχι αγώνες που δεν ανοίχτηκαν ποτέ για υπολογισμό.

Στο **Ιστορικό & αποτελέσματα → Πλήρης καταγραφή για ανάλυση**, πάτησε **Ετοιμασία αρχείου ανάλυσης** και μετά **Λήψη πλήρους αρχείου ανάλυσης JSON**. Το `basketball_analysis_backup.json` περιλαμβάνει ολόκληρο το προσωπικό ιστορικό επιλογών, την κρυφή καταγραφή από τη βάση και τυχόν πραγματικές καταγραφές της ανοιχτής συνεδρίας που περιμένουν αποθήκευση. Δεν εμφανίζεται πίνακας της κρυφής καταγραφής και δεν τροποποιούνται εγγραφές. Οι λήψεις της βάσης γίνονται μόνο μετά το πάτημα του κουμπιού. Το παλιό απλό backup επιλογών παραμένει διαθέσιμο.

Για αξιολόγηση όλων των υπολογισμών χρησιμοποίησε αυτή την ενιαία εξαγωγή και όχι μόνο το απλό backup. Απουσία αποθηκευμένων υπολογισμών δηλώνεται ρητά· δεν δημιουργείται αναδρομικό ιστορικό προβλέψεων. Η νέα επιλογή εξαγωγής χρησιμοποιεί τον υπάρχοντα μηχανισμό/SQL της καταγραφής, χωρίς νέο migration.


## BASKET-2026-11-08-CARDS1 — κάρτες αποδόσεων

Οι έξι αγορές εμφανίζονται ανά δύο σε τρεις σειρές: **1 / 2**, **Handicap1 / Handicap2**, **Over / Under**. Κάθε κάρτα δείχνει την τιμή, την πραγματική γραμμή όπου απαιτείται και το όνομα της ομάδας. Οι δύο κάρτες κάθε σειράς παραμένουν δίπλα-δίπλα σε κινητό. Πηγή/εταιρεία/ώρα λήψης διατηρούνται στη βοήθεια της κάρτας και στην ενότητα «Πηγές αποδόσεων».

Οι απουσίες αφαιρέθηκαν από τη φόρμα και τις εμφανιζόμενες στήλες ιστορικού/CSV. Οι υπάρχουσες εγγραφές και τα πλήρη αντίγραφαJSON διατηρούνται. Οι νέες επιλογές δεν περιέχουν καταχωρισμένες απουσίες. Δεν αλλάζουν οι πηγές αποδόσεων, τα μοντέλα, τα όρια δειγμάτων, το ιστορικό ή η εκκαθάριση. Δεν απαιτείται SQL.

Ελέγχθηκαν υπολογισμός/αποθήκευση, σωστά signedhandicaps/OverUnder, χειροκίνητη καταχώριση και διάταξη πραγματικού Streamlit σε1280,375 και320px με ελεγχόμενα δεδομένα. Τα τεστ δεν είναι πραγματικές νέες λήψεις τιμών ή στοιχηματικές επιλογές.

## Αντιστοίχιση ονομάτων Ευρωλίγκας — 06/11/2026

Διορθώθηκαν οι καταγεγραμμένες ονομασίες Paf `KK Crvena Zvezda Belgrade`, `Partizan Belgrade` και η ακριβής αλλοιωμένη γραφή `Å½algiris Kaunas` από το αρχείο της πηγής. Ελέγχθηκαν οι γνωστές γραφές και των20 ομάδων σε επίσημη πηγή, Sofascore και Paf, με απόρριψη διαφορετικών ομάδων, αντίστροφης έδρας, λάθος ώρας ή διοργάνωσης. Δεν χρησιμοποιείται ασαφής αναζήτηση ονομάτων. Η cache αναζήτησης αποδόσεων ανανεώθηκε ώστε να μη διατηρεί τα προηγούμενα αποτυχημένα αποτελέσματα.

Το `check_paf_browser.py` με το προαιρετικό πραγματικό αρχείο του χρήστη επαληθεύει τοπικά και τους4 αγώνες Ευρωλίγκας του καταγεγραμμένου listing. Αυτό είναι replay παλιότερης απόκρισης, όχι επιβεβαίωση σημερινών τιμών ή live κάλυψης όλων των αγορών. Οι τιμές του αρχείου δεν εισάγονται στην εφαρμογή. Το `check_euro_odds.py` ελέγχει και τις20 ομάδες και380 λανθασμένα ζεύγη. Η χειροκίνητη αποθήκευση παραμένει ως έχει: χρειάζονται εταιρεία, πραγματική απόδοση/γραμμή, επιλογή αγοράς και μελλοντικός αγώνας. Το αποθηκευμένο ιστορικό δεν αλλάζει.

## Ελληνική Basket League — 06/11/2026

Για την Ελλάδα προηγείται πλέον το επίσημο πρόγραμμα/αποτελέσματα του [ΕΣΑΚΕ](https://www.esake.gr/el/action/EsakePrograms), με εναλλακτική το Sofascore. Δεν απαιτείται νέο κλειδί. Η επιλογή ημερομηνίας αφορά Europe/Athens· επίλεξε 07/11 ή 08/11 για τους αντίστοιχους αγώνες του Σαββατοκύριακου. Δεν καταχωρίζονται στατικοί αγώνες στον κώδικα.

Η πηγή διαβάζει την πραγματικά επιλεγμένη διοργάνωση/σεζόν, τις ομάδες με τα επίσημα αναγνωριστικά τους και τις δημοσιευμένες ώρες. Ασαφείς ώρες/TBA και άγνωστες σεζόν απορρίπτονται. Η ανάγνωση των επιλογών υποστηρίζει τα HTML defaults (πρώτη επιλογή όταν δεν υπάρχει selected), διαφορετικό id/name του πεδίου και προαιρετικά κλεισίματα option. Αν υπάρχει αρχική κενή επιλογή, η σεζόν γίνεται δεκτή μόνο με μοναδικό επιβεβαιωμένο τίτλο GBL που συμφωνεί με τον κατάλογο. Αν το πρόγραμμα δεν παρέχει επαληθεύσιμη φόρμα, δοκιμάζεται και το επίσημο EsakeResults. Η ζητούμενη σεζόν/φάση εξακολουθεί να ελέγχεται σε κάθε αγωνιστική. Το τρέχον πρόγραμμα επαναχρησιμοποιείται από cache 120s. Για άλλες ημερομηνίες και ιστορικό αναζητούνται οι δημοσιευμένες αγωνιστικές/φάσεις της σεζόν, με περιορισμένη παράλληλη ανάκτηση και cache 600s. Το μοντέλο χρησιμοποιεί όσους διαθέσιμους προηγούμενους ολοκληρωμένους αγώνες βρίσκει ανά ομάδα, με όριο τους10 πιο πρόσφατους και ελάχιστο1 ανά ομάδα· δεν συμπληρώνει υποθετικά αγώνες. Ο ΕΣΑΚΕ παρέχει πρόγραμμα/αποτελέσματα, όχι αποδόσεις στοιχηματικών.

Διορθώθηκε και το φίλτρο Sofascore: αναγνωρίζει το σταθερό αναγνωριστικό της ανδρικής διοργάνωσης 304 και τις ονομασίες `stoiximan-basket-league` / `stoiximan-gbl`, με έλεγχο χώρας, αποκλείοντας άλλες διοργανώσεις όπως το κύπελλο 608.

`python check_greek_basket.py`: ελεγχόμενες HTML σελίδες σύμφωνα με τη δημοσιευμένη δομή του ΕΣΑΚΕ, 5 αγώνες Σαββάτου/2 Κυριακής, ώρες Ελλάδας, σεζόν, αναγνωριστικά, άγνωστη ώρα, archive/result/history, cache/fallback και Streamlit UI. Οι ονομασίες/ώρες του επίσημου προγράμματος 7–8 Νοεμβρίου επιβεβαιώθηκαν μέσω δημόσιας ανάγνωσης. **Η ζωντανή HTTP ανάκτηση του ΕΣΑΚΕ από το περιβάλλον ανάπτυξης αποκλείεται από την πολιτική δικτύου· δεν έχει επιβεβαιωθεί ακόμη από τη φιλοξενούμενη εφαρμογή.** Το Sofascore επιστρέφει HTTP 403 challenge εδώ. Αποτυχίες εμφανίζονται στην «Κατάσταση πηγών», χωρίς παράκαμψη πρόσβασης ή υποθετικά δεδομένα.

Προηγούμενη έκδοση: [backup/before-greece-2026-11-06](https://github.com/mgiobaras/basketballbet/tree/backup/before-greece-2026-11-06).

## Εμφάνιση ιστορικού — 05/11/2026

Λευκό θέμα με πράσινες λεπτομέρειες και διακριτικό σχέδιο γηπέδου μπάσκετ. Τα Κερδισμένα / Χαμένα / Εκκρεμή εμφανίζονται σε μία σειρά και σε μικρή οθόνη. Οι επιστροφές παραμένουν χωριστές και εξαιρούνται από την επιτυχία. Το ιστορικό και το CSV ταξινομούνται κατά έναρξη από παλαιότερη σε νεότερη και, στην ίδια ώρα, κατά μεγαλύτερη αρχική πιθανότητα. Η ώρα εμφανίζεται σε Europe/Athens· οι αρχικές πιθανότητες/εγγραφές δεν αλλάζουν. Η επιλογή αγώνα διατηρείται με το αναγνωριστικό του ακόμη και αν αναδιαταχθεί η πηγή.

Δεν αλλάζουν υπολογισμοί, αποδόσεις, βάση ή Secrets. Πλήρες αντίγραφο προηγούμενης έκδοσης: [backup/before-ui-2026-11-05](https://github.com/mgiobaras/basketballbet/tree/backup/before-ui-2026-11-05). Έλεγχοι: `python check_history_ui.py`, `python check_basketball.py`, `python check_pace.py`.

## Προαιρετικό μοντέλο ρυθμού και αποτελεσματικότητας — 03/11/2026

Στο «Μοντέλο υπολογισμού» παραμένει προεπιλεγμένο το κλασικό μοντέλο. Η επιλογή «Ρυθμός & αποτελεσματικότητα — πειραματικό» προσθέτει αναλυτικά ομαδικά στατιστικά για NBA και Ευρωλίγκα. Δεν έχει αποδειχθεί βελτίωση ακρίβειας ή κερδοφορίας.

- Χρησιμοποιεί τους ίδιους διαθέσιμους έως10 πιο πρόσφατους ολοκληρωμένους αγώνες ανά ομάδα, στην ίδια διοργάνωση και πριν από την έναρξη του επιλεγμένου αγώνα. Αν λείπει κάποιο αναλυτικό box score, δεν αντικαθιστά τον αγώνα με παλαιότερο και δεν κατασκευάζει τιμές. Μπορείς να επιλέξεις το κλασικό μοντέλο.
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
- Ελλάδα: πρόγραμμα/αποτελέσματα ΕΣΑΚΕ → Sofascore. Αποδόσεις Sofascore → Paf, όταν δημοσιεύονται. Ο ΕΣΑΚΕ δεν ερωτάται για τιμές στοιχηματικών. Αποτυχίες εμφανίζονται χωρίς υποθετικές αποδόσεις ή γραμμές.

Οι διαφορετικές πηγές συνδέονται μόνο με ίδια διοργάνωση, γηπεδούχο/φιλοξενούμενο, ακριβή ονόματα/ρητά aliases και πραγματική ώρα έναρξης. Δεν γίνεται fuzzy αντιστοίχιση. Σκορ που διαφωνούν ή αμφίβολη ταυτότητα σταματούν τον υπολογισμό.

Οι αποδόσεις και τα **Over/Under lines και signed handicaps** εισάγονται μαζί από την ίδια καταγραφή. Κάθε αγορά διατηρεί το δικό της line, εταιρεία/δημοσιευμένο ID παρόχου, πηγή, event, URL και πραγματική ώρα λήψης. Τα θετικά/αρνητικά handicap αφορούν τη συγκεκριμένη πλευρά. Δεν αντιγράφεται η ίδια προσημασμένη γραμμή στην άλλη ομάδα.

Οι αγορές αφορούν ολόκληρο τον αγώνα **μαζί με παράταση**. Αγορές περιόδου ή ασαφούς scope δεν εισάγονται. Το ESPN μπορεί να δίνει `current` ή μόνο δημοσιευμένο `close` snapshot: η εφαρμογή τα επισημαίνει χωριστά, δεν τα παρουσιάζει ως εγγυημένες ζωντανές/εκτελέσιμες τιμές και δεν χρησιμοποιεί opening τιμές ως current. Από το Sofascore γίνονται δεκτές μόνο αγορές με ρητή ένδειξη παράτασης. Αν δεν δίνεται όνομα εταιρείας, εμφανίζεται το πραγματικό ID παρόχου ως μη δηλωμένη εταιρεία, χωρίς επινόηση ονόματος.

Ελλείψεις μένουν κενές. Δεν υπάρχει προεπιλεγμένη απόδοση1,90, line165,5 ή handicap−3,5. Υπάρχει προαιρετική χειροκίνητη καταχώριση πραγματικών τιμών με υποχρεωτική εταιρεία.

## Πρόβλεψη

Χρησιμοποιούνται οι **διαθέσιμοι έως10 πιο πρόσφατοι πραγματικοί ολοκληρωμένοι αγώνες ανά ομάδα στην ίδια διοργάνωση**, πριν από τον επιλεγμένο αγώνα. Με5 αγώνες χρησιμοποιούνται5· αν η άλλη ομάδα έχει3, χρησιμοποιούνται οι δικοί της3. Με περισσότερους από10 επιλέγονται πάντα οι10 νεότεροι. Αν μια ομάδα δεν έχει κανέναν έγκυρο προηγούμενο αγώνα, ο υπολογισμός απέχει. Η εφαρμογή εμφανίζει το πραγματικό πλήθος ανά ομάδα και ένδειξη μικρότερου δείγματος.

Σταθμισμένοι πόντοι υπέρ/κατά με ημιζωή90 ημερών, μέσος της επίθεσης της ομάδας και της άμυνας του αντιπάλου. Οι διακυμάνσεις προέρχονται από τις ίδιες παρατηρήσεις. Το πειραματικό μοντέλο χρησιμοποιεί ανεξάρτητη Normal προσέγγιση των πόντων, με διόρθωση ακέραιων σκορ και χωριστή πιθανότητα επιστροφής σε ακέραια γραμμή. Δεν μεταφέρεται η Poisson ποδοσφαίρου σε πόντους μπάσκετ. Δεν υπάρχουν υποθετικοί μέσοι όροι ομάδων, σταθερό πλεονέκτημα έδρας, συντελεστές ξεκούρασης, τεχνητά κατώφλια σκορ/διακύμανσης ή Kelly.

Η ενότητα απουσιών έχει αφαιρεθεί. Οι παλιές εγγραφές παραμένουν στα πλήρη αντίγραφαJSON χωρίς μεταβολή.

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
εναλλακτική για αποδόσεις Ευρωλίγκας και ελληνικής Basket League. Στην Ευρωλίγκα ακολουθεί το προαιρετικό The Odds API.
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

### Greek automatic odds: GREECE-ODDS1

ESAKE supplies fixtures/results, not bookmaker prices. Previously Greece tried
only ESAKE's empty quote method and Sofascore; Paf was gated to EuroLeague.
The quote route now skips ESAKE and tries Paf after Sofascore for Greece. No
new key is needed for this existing public Paf route. The Odds API remains
limited to the previously verified NBA/EuroLeague sport keys.

Explicit Greek/English club aliases cover all 14 clubs in the official 2026/27
programme, including current ESAKE sponsor labels. Display names and saved
history are not rewritten. Paf Greek events require Greece plus an explicit
GBL/A1/Basket League identity (or the explicit Greek Basket League label).
Women's, cup, lower-division and youth classifications are rejected. Home/away,
exact kickoff, unique match, open full-game overtime markets, prices and signed
lines remain attached to their own source event. Missing data stay missing.
The existing Paf diagnostics download includes the actual listing labels and
country/competition path when an event cannot be matched.

`python check_greek_odds.py` passed for all 14 club identities, all seven
programme pairings, six markets/real-schema units, no synthetic missing lines,
Sofascore-403 fallback, two-stage Paf retrieval, cached diagnostics, duplicate
match rejection, selected-event persistence and automatic Streamlit metrics.
These are controlled Greek events built with an already recorded Kambi market
schema; they are not a live Paf Greek odds capture. Existing EuroLeague alias,
Paf real-response and basketball model/storage/UI checks also passed. The live
Paf Greek listing/availability must still be confirmed in the hosted app; no
network block was bypassed and no current Greek price is claimed here.

### Browser fallback: BROWSER-ODDS1

The owner opened the exact public Paf URL in their browser and supplied a valid
103-event JSON while Streamlit's server received HTTP410. This proves the URL
was not globally retired. The supplied listing contained four EuroLeague games
and no Greek events, with `soonMode=HOURLY`; it ended at 07/11 08:30 UTC, before
the first Greek fixture. The upload is test evidence only and is never used as
current application odds or committed to this repository.

Greek requests now use the country-scoped Kambi list route
`/listView/basketball/greece/all/all/matches.json`. Server/global and country
list caches are distinct. If the server's Paf request reports HTTP410, a small
native Streamlit component asks the user's browser to fetch that public listing
and, after server-side fixture matching, the same event's detailed markets.
This is automatic; no file import, new key, browser extension or account login
is required. The existing Python Paf parser remains authoritative for league,
country, exact kickoff, home/away, unique match, overtime scope, main lines and
prices. No page script or vendor HTML is executed.

The component receives only a fixed allowlisted Paf API URL, four public request
parameters and a generated request ID. It sends no app secrets, cookies,
authorization headers or bet history. Browser fetch uses normal CORS,
`credentials=omit`, HTTPS and a 20-second timeout. It does not use proxies,
alternate hosts, spoofed headers or overrides of provider/browser restrictions.
If CORS or an HTTP error blocks it, the app reports the failure and keeps odds
missing. Successful navigation to the JSON URL alone does not prove CORS works
from a Streamlit iframe; that remains a live-hosted verification item.

Server receipt time is assigned once when the component response arrives and is
preserved on reruns. Browser-derived quotes carry
`price_kind=published_pre_match_browser`. Cache and nonce scope include the
selected fixture's identity and refresh version, and replies from an earlier
request/fixture are ignored. Browser/server snapshots use separate cache keys.
The Paf diagnostics download includes the browser path and its result/error.

Validation: `python check_paf_browser.py` checks the staged transport and actual
Streamlit app reruns with mocked component responses. Optional `--frontend`
uses Chromium to execute the real HTML/JavaScript with an offline fetch stub,
checking URL allowlisting, deduplication, errors, postMessage and omitted
credentials. An optional owner-listing path replays all103 source events and
confirms that no Greek prices can be extracted from that particular response.
Existing basketball, Greek/EuroLeague alias, recorded Paf and actual ESAKE
capture checks also pass. These checks do not claim a live Paf CORS response or
Greek prices; the country listing's live availability must be confirmed in the
hosted application. Selected bets/history/models/database setup are unchanged.

### Available history: HISTORY-FLEX1

The ten-game minimum is removed from the shared basketball analysis function.
Each team uses its independently selected latest 1..10 completed games in the
same competition before the target kickoff. Existing source retrieval/fallback
rules are unchanged; missing observations are not padded, duplicated or replaced
with synthetic priors. `recent_games` still sorts by kickoff descending and
caps at10, so every newly observed qualifying game can replace the oldest when
the window is full. No training or retrospective rewriting is performed.

Weighted means and empirical variances use the actual available observations;
the formulas for a full ten-game sample remain numerically unchanged. Model
snapshots now include `history_counts` and versions `basket-up-to10-normal-v2`
and `basket-up-to10-possessions-v2`. Pace mode remains limited to NBA/EuroLeague
and requires verified box scores for every selected available game; it does
not replace missing recent box scores with older games. The UI shows per-team
sample counts, explains smaller samples and distinguishes missing history from
missing/unsupported pace statistics. Existing model-mode widget values migrate
safely and calculation state uses new model keys.

`python check_available_history.py` passed:5/5 and5/3 observations, independent
hand-calculated expected means, minimum1 and zero-history abstention, future and
wrong-league exclusion, deduplication,11+ observations and replacement of the
oldest game, finite normalized distributions, short pace samples with complete
box scores, and Greek Streamlit calculation/log/save with5 games. An existing
v1 selected-bet record remains unchanged after the new analysis
and save. Existing basketball and pace checks also passed. Source prices,
browser odds retrieval, saved probabilities, past history and SQL are unchanged.

### ESAKE history retrieval: HISTORY-FETCH1

The owner reported zero history for Doxa/Aris and an ESAKE secure-connection
failure after the minimum-sample change. Previously history loaded entire
current/previous seasons, including unplayed phases. Any archive exception
aborted that adapter and discarded already retrieved results.

Greek history now starts with the normal, verified EsakeResults page and keeps
completed observations from the selected fixture's season/championship before
its kickoff. It requests relevant earlier round pages sequentially, skipping a
round only when both target teams already have a verified result there. For
playoffs it also checks the regular season. It does not fetch a previous season
just to fill ten slots or query future playoff phases for a regular-season game.
Each failed round adds a source note and diagnostic; other valid observations
remain usable. Wrong season/phase/round pages are still rejected. Genuine score
or identity conflicts stop calculation rather than being silently reconciled.

The model still chooses its latest ten by kickoff date, not round number, so a
postponed early-round match played recently can enter the window. The history
scan does not stop as soon as ten numeric rounds have been seen. Verified round
pages cache for600 seconds; the normal latest-results page caches for120 seconds.
ESAKE bypasses the old combined six-hour history cache, allowing a previously
empty/partial response to recover on a later calculation. Other sports adapters
keep their existing cache. No table/history migration or bet changes are made.

`python check_esake_history.py [owner-esake-diagnostics.json]` passed for archived
connection failures, preservation of verified recent results, current-season
5/5 recovery, stale empty-cache bypass, correct actual home/away orientation,
per-round cache reuse, delayed early-round games in the latest-ten window,
duplicate URL isolation, conflicting-score rejection, zero-data abstention and
Greek Streamlit calculation/logging. With the owner's real default results
capture, one completed game per target team survives failures of all other
archive requests; the 5/5 archive recovery is exercised with controlled pages.
The application never loads the uploaded capture as production history. These
are replay/failure-injection checks, not proof that ESAKE's live connection is
always available. If every request fails and no verified cache exists, history
correctly remains unavailable. Diagnostics retain at most four public response
bodies, while all error notes remain visible.
