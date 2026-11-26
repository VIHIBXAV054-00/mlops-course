1.
A random generált "beállítások" függnek tőle mint hogy hogyan generáljuk a train/test splitet.
Ennek változtatásának hatására más-más adat sorok kerülnek a train/test halmazokba így természetesen változhat a test spliten elért teljesítmény.
Mivel egy szerencsés seed megtalálásával jobb teljesítmény értékeket fogunk kapni de ez nem feltétlen tényleges teljesítmény növekedéssel jár "valós" adatokon illetve nem lesz reprodukálható.

2.
Mivel így a folyamat elején fail-el egy olyan hibán amin késöbb mindenképp fail-elt volna de így erőforrásokat takarítunk meg ami feleslegesen futott volna.