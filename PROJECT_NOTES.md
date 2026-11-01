# BasketballBet — συνέχεια εργασίας

## Αίτημα και στόχος
- Repository mgiobaras/basketballbet, branch main, entrypoint app.py. Χρησιμοποιούμε /workspace/basketballbet, χωρίς νέο worktree εκτός ρητού αιτήματος.
- Ο χρήστης ζήτησε όλες τις αντίστοιχες αλλαγές της εφαρμογής ποδοσφαίρου, συμπεριλαμβανομένου υπολογισμού πρόβλεψης, αυτόματης εναλλαγής πηγών, αποδόσεων, μόνιμης αποθήκευσης/αποτελεσμάτων και αυτόματου Over line/handicap. Απουσίες χειροκίνητες.
- Διατηρούνται NBA, EuroLeague και Ελλάδα – Basket League. Καμία επινόηση δεδομένων και καμία υπόσχεση επιτυχίας70% ή κερδοφορίας.

## Υλοποίηση 2026-11-01 — BASKET-AUTO1
- Αρχική app.py διατηρείται αυτούσια στο baseline/app_original.py. Αφαιρέθηκαν AUTO_TEAMS_DB, fuzzy team matching, υποθετικά1,90/165,5/−3,5, Kelly και αυθαίρετες προσαρμογές έδρας/ξεκούρασης/απουσιών.
- basketball_data.py: αυτόματες πηγές NBA ESPN→Sofascore, EuroLeague official API→Sofascore→ESPN, Ελλάδα Sofascore. Δεν υπάρχει δεύτερος επαληθευμένος ελληνικός δημόσιος adapter. Άγνωστες/μπλοκαρισμένες πηγές εμφανίζονται με σαφή αποχή, χωρίς προσποίηση κάλυψης.
- Ακριβής ταυτότητα διοργάνωσης, ημερομηνίας/ώρας, home/away και IDs. Μόνο ρητά καταγεγραμμένα aliases. Διπλά παιχνίδια δεν διπλομετρώνται, συγκρουόμενα σκορ ή αμφίβολες ώρες σταματούν τον υπολογισμό. Η επιλογή ημέρας αφορά Europe/Athens, λαμβάνοντας υπόψη τα NBA παιχνίδια μετά τα μεσάνυχτα UTC.
- Κάθε γραμμή/απόδοση αποτελεί ενιαία καταγραφή: market, signed line, decimal odds, named bookmaker ή πραγματικό provider ID όταν δεν παρέχεται όνομα, πηγή, URL, event, receipt, scope. Όλες οι υποστηριζόμενες αγορές έχουν παράταση. Ασαφή periods δεν εισάγονται. ESPN current/close snapshots επισημαίνονται, δεν χρησιμοποιούνται open τιμές ως current.
- basketball_model.py: μόνο τελευταίοι10 πραγματικοί ολοκληρωμένοι αγώνες ανά ομάδα στην ίδια διοργάνωση πριν από kickoff, βάρη ημιζωής90 ημερών, επίθεση/άμυνα και εμπειρικές διακυμάνσεις. Προσαρμογή σε basketball με πειραματική Normal πόντων, όχι ποδοσφαιρική Poisson. Χωριστές πιθανότητες win/push/loss σε ακέραιες γραμμές. Δεν έγινε backtest/βαθμονόμηση της νέας εκδοχής.
- Απουσίες: χειροκίνητα βασικοί/αναπληρωματικοί, δείκτης−1/−0,5 αποθηκεύεται μόνο. Άγνωστο δεν μετατρέπεται σε μηδέν.
- basketball_store.py και database/supabase_setup.sql: SQLite ή private Supabase σε χωριστούς basketball πίνακες, χωρίς αλλαγή football πινάκων. Login πριν από remote πρόσβαση, server secret/service_role μόνο, χωρίς silent fallback σε τοπική βάση. Αμετάβλητες αρχικές τιμές/γραμμές, μοναδική αγορά/αγώνας,1 μονάδα, απόδοση≥1,50, όχι μετά την έναρξη, receipt≤5 λεπτών.
- Αυτόματη εκκαθάριση όταν ανοίγει/χρησιμοποιείται η εφαρμογή, όχι background scheduler. Πραγματικό τελικό σκορ περιλαμβάνει παράταση· ισοπαλία σε ακέραιη γραμμή επιστρέφει τη μονάδα. Pending δεν μετρά σε ROI/επιτυχία. CSV/JSON εξαγωγές και χωριστή διατήρηση παλιού CSV χωρίς αναδρομική επαλήθευση.
- Προστέθηκαν σωστό requirements.txt, README, secrets example, run_windows.bat. Διατηρήθηκε το παλιό requirements.txt.txt για αναφορά. Ενεργοποιούνται τα κανονικά CORS/XSRF defaults στη devcontainer εκκίνηση.

## Επαλήθευση
- check_basketball.py πέρασε: αποκλεισμός μελλοντικών/άλλης διοργάνωσης/παλιότερων απόlast10, αποχή σε μικρό δείγμα, ακριβή IDs, line/odds snapshots, λάθος αγώνας/ομάδα, αυτόματο fallback, refunds, immutable duplicate, stale/late rejection, legacy CSV και UI χωρίς επιλογή πηγής με χειροκίνητες απουσίες. Πρόκειται για ελεγχόμενα δεδομένα, όχι ιστορικό backtest.
- check_cloud_storage.py πέρασε σε πραγματικά PostgreSQL17/PostgREST12 containers: επαναλήψιμο SQL, service-role πρόσβαση, anon/authenticated denial, duplicate isolation, αρχικό line, επιστροφή, cache και ιστορικό μετά από restart. Ο test harness διορθώθηκε για TCP readiness και δυναμικό Docker port μετά το restart.
- Live NBA espn:401909903:6 αγορές, Over/Under221,5, handicap γηπεδούχου+7,5/φιλοξενούμενου−7,5,10 πραγματικοί αγώνες ανά ομάδα και πρόβλεψη. Επιβεβαιώθηκε αποθήκευση του αρχικού πραγματικού quote σε προσωρινή SQLite, χωρίς τοποθέτηση στοιχήματος. Ημέρα Europe/Athens:7 αγώνες με σωστή τοπική ημερομηνία.
- Streamlit server ξεκίνησε, health HTTP200 ok, και σταμάτησε μετά τον έλεγχο. Live NBA AppTest άνοιξε και υπολόγισε με πραγματικές πηγές, χωρίς exceptions. Δεν υπάρχει επαληθευμένο hosted app URL στο checkout.

## Εξωτερικές εκκρεμότητες
- Η ενεργή πολιτική περιβάλλοντος αποκλείει api-live.euroleague.net και api.sofascore.com. Αποθηκεύτηκαν τα νέα domains μαζί με www.sofascore.com στο draft, διατηρώντας τα προϋπάρχοντα. Χρειάζεται Save/Publish από τον χρήστη και μετά νέος live έλεγχος EuroLeague/Ελλάδας. Το save δεν εφαρμόζει ούτε δημοσιεύει runtime αλλαγές. Δεν εγγυόμαστε ότι οι πάροχοι θα επιτρέψουν ή θα καλύπτουν όλες τις αγορές μετά την άρση του περιορισμού.
- Για μόνιμη αποθήκευση της hosted basketball εφαρμογής χρειάζεται μία φορά το νέο basketball SQL και τα δικά της Streamlit Secrets όπως στο README. Δεν έχουμε/δεν ζητήσαμε κλειδιά στη συνομιλία και δεν τροποποιήσαμε hosted βάση ή Secrets.
- Η υπάρχουσα εφαρμογή αναμένεται να χρησιμοποιεί main/app.py. Push μπορεί να ενεργοποιήσει αυτόματο Streamlit deploy, αλλά το πραγματικό hosted version δεν έχει επαληθευτεί.
