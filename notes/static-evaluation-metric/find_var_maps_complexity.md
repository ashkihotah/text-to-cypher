# Complexity

Il problema di trovare la mappatura ottimali tra due `GraphPattern` si classifica formalmente come un **Constraint Optimization Problem (COP)**, che è una specializzazione dei Constraint Satisfaction Problems (CSP).

Più specificamente, in letteratura matematica e informatica, questo è noto come il problema del **Maximum Common Subgraph (MCS)** o, in una variante leggermente diversa, il calcolo della **Graph Edit Distance (GED)**.

Ecco come scomporre la classificazione:

### 1. È un Constraint Satisfaction Problem (CSP)?
**Sì, ma con una "twist".**
Un CSP classico cerca una soluzione che soddisfi tutti i vincoli "rigidi" (Hard Constraints).

*   **Variabili:** I nodi del grafo sorgente ($S_1, S_2, ...$).
*   **Domini:** I nodi del grafo target ($T_1, T_2, ...$).
*   **Vincolo Rigido (Hard):** Iniettività (Vincolo `AllDiff`). Non puoi mappare due nodi sorgente sullo stesso nodo target.
*   **Vincolo Strutturale (Hard/Soft):** Se $S_1$ è collegato a $S_2$, allora $f(S_1)$ deve essere collegato a $f(S_2)$.

Nel tuo caso, poiché stai cercando di massimizzare una `score_fn` (somiglianza), i vincoli strutturali non sono "rigidi" (se non c'è l'arco, la mappatura è valida ma ha un punteggio basso). Questo trasforma il problema da puro CSP a **COP (Constraint Optimization Problem)**.

### 2. È un Problema di Ricerca nello Spazio degli Stati?
**Sì, dal punto di vista risolutivo.**
Puoi modellare il problema come l'esplorazione di un albero di ricerca:
*   **Stato Iniziale:** Mappatura vuota `{}`.
*   **Stato Successivo (Action):** Scegli il prossimo nodo sorgente non assegnato e mappalo a un nodo target disponibile.
*   **Stato Finale:** Tutti i nodi sorgente sono assegnati.
*   **Costo/Guadagno:** Il valore della tua `score_fn`.

Attualmente il tuo codice esegue una **Ricerca Esaustiva (Brute Force)** o **Generate and Test**: generi tutti gli stati finali possibili (le foglie dell'albero) e li valuti uno a uno.

### 3. La Classificazione più Precisa: Quadratic Assignment Problem (QAP)
Questo è il motivo per cui il problema è computazionalmente difficile (NP-Hard).
Non è un semplice problema di assegnazione lineare (come assegnare lavoratori a compiti, risolvibile in $O(n^3)$ con l'algoritmo Ungherese).

È **Quadratico** perché il "guadagno" di mappare il Nodo $A$ sul Nodo $X$ non è indipendente, ma **dipende da dove mappi i vicini di A**.
*   Se mappi $A \to X$, il punteggio aumenta solo se mappi anche il vicino $B$ su un vicino di $X$ ($Y$).
*   La funzione di costo dipende dalle interazioni tra coppie di assegnazioni.

---

### Come questa classificazione ti aiuta a risolverlo?

Sapere che è un problema di ricerca su un **COP** ti suggerisce di abbandonare le permutazioni pure (`itertools.permutations`) e adottare algoritmi di **Backtracking con Pruning (Branch and Bound)**.

Invece di generare *tutte* le permutazioni, costruisci la soluzione passo dopo passo e "tagli" (pruning) i rami che non promettono bene.

#### Esempio di Algoritmo Migliorato (Branch & Bound):

Immagina di voler mappare:
*   Source: `(A:Person)-[:KNOWS]->(B:Person)`
*   Target: `(X:Movie), (Y:Movie)`

1.  **Step 1:** Mappi `A -> X`.
2.  **Check (Lookahead/Heuristic):** `A` è una `Person`, `X` è un `Movie`.
3.  **Pruning:** Il punteggio parziale è già disastroso (o 0, se usi vincoli rigidi sulle label).
4.  **Azione:** Non provi nemmeno a mappare `B`! Torni indietro (backtrack) e provi `A -> Y`.

### Algoritmi Noti in Letteratura
Se volessi implementare lo stato dell'arte per questo tipo di problema AI, guarderesti a:

1.  **VF2 / VF3 Algorithm:** Gli algoritmi standard de-facto per l'isomorfismo di sottografi. Usano euristiche di "lookahead" (guardare i vicini) per tagliare l'albero di ricerca prestissimo.
2.  **A* (A-Star) Search:** Se stai cercando la **Graph Edit Distance**, A* con un'euristica ammissibile può trovare la soluzione ottima senza esplorare tutto lo spazio.

**In sintesi:** Stai affrontando un problema **NP-Hard** di **Ottimizzazione Combinatoria**. Dato che i tuoi grafi sono piccoli ($N < 10$), un approccio di ricerca nello spazio degli stati con **Backtracking** (come suggerito nella mia risposta precedente ottimizzando l'iterazione nodi-archi) è sufficiente e molto più efficiente della forza bruta pura.

# Possible solutions

Ecco una panoramica completa di tutti i modi possibili per risolvere il problema del **Maximum Common Subgraph / Graph Edit Distance**, ordinati dal più "esatto" al più "approssimato", con riferimento alla fattibilità nel tuo caso specifico ($N < 10$).

---

### 1. Metodi Esatti (Optimal Solutions)
Questi metodi garantiscono di trovare la mappatura migliore in assoluto, ma differiscono per efficienza.

#### A. Backtracking con Pruning (Branch & Bound)
È l'evoluzione diretta del tuo approccio attuale. Invece di generare *prima* tutte le permutazioni e *poi* testarle, costruisci la mappatura nodo per nodo.
*   **Come funziona:**
    1.  Mappa il nodo $u_1$ su $v_1$. Calcola il costo parziale.
    2.  Se il costo parziale supera già il costo della migliore soluzione trovata finora (Upper Bound), **taglia (prune)** quel ramo. Non provare a mappare $u_2, u_3...$
*   **Vantaggio:** Drastica riduzione dello spazio di ricerca.
*   **Strumento:** Implementabile a mano in Python.

#### B. Algoritmi dedicati all'Isomorfismo (VF2 / VF3)
Sono lo standard accademico per il pattern matching nei grafi.
*   **Come funziona:** Usano regole di "fattibilità" (look-ahead) molto aggressive. Prima di mappare il nodo A su B, controllano se i vicini di A sono compatibili con i vicini di B.
*   **Implementazione:** La libreria Python **`networkx`** implementa `isomorphism.GraphMatcher` basato su VF2. Potresti adattarlo per cercare non l'isomorfismo perfetto, ma la massima sovrapposizione.

#### C. Riduzione a Maximum Clique
È un trucco matematico elegante.
*   **Come funziona:** Costruisci un "Grafo di Associazione" dove ogni nodo rappresenta una possibile coppia `(u, v)` (un'associazione tra nodo sorgente e target). Colleghi due nodi in questo nuovo grafo se le associazioni sono compatibili.
*   **Risultato:** Trovare la **Maximum Clique** (il sottografo completo più grande) nel grafo di associazione equivale a trovare il Maximum Common Subgraph.
*   **Librerie:** Algoritmo di Bron-Kerbosch (presente in `networkx`).

#### D. Programmazione Lineare Intera (ILP - Integer Linear Programming)
Trasformi il problema in equazioni matematiche.
*   **Come funziona:** Definisci una matrice binaria $X$ dove $x_{ij} = 1$ se il nodo $i$ è mappato su $j$. Definisci vincoli lineari (es. $\sum x_{ij} = 1$) e una funzione obiettivo da massimizzare.
*   **Solver:** Gurobi, CPLEX, o **Google OR-Tools** (gratuito).
*   **Pro:** Risolve in millisecondi problemi piccoli.
*   **Contro:** Overhead di setup elevato per grafi minuscoli.

---

### 2. Metodi Euristici / Approssimati (Sub-Optimal Solutions)
Questi metodi sacrificano la garanzia di trovare la soluzione perfetta in cambio di una velocità estrema ($O(N^3)$ o $O(N^2)$ invece di fattoriale).

#### A. Algoritmo Ungherese (Bipartite Matching) con Rilassamento
Questo è uno dei metodi più potenti per il Graph Edit Distance approssimato (usato ad esempio nell'algoritmo **GED-Beam**).
*   **Il problema:** Mappare nodi e archi simultaneamente è quadratico (difficile).
*   **Il trucco:** Ignoriamo temporaneamente la struttura degli archi. Calcoliamo solo una "matrice di costo" tra ogni nodo $u$ e ogni nodo $v$ basandoci sulle loro etichette e gradi locali.
*   **Risoluzione:** Usiamo l'algoritmo di **Munkres (Algoritmo Ungherese)** (in `scipy.optimize.linear_sum_assignment`) per trovare l'assegnazione che minimizza il costo locale.
*   **Complessità:** $O(N^3)$. Velocissimo. Spesso trova la soluzione ottima o quasi ottima.

#### B. Greedy Search (Hill Climbing)
*   **Come funziona:**
    1.  Prendi il nodo sorgente "più difficile" (es. grado più alto, etichette rare).
    2.  Mappalo al miglior candidato nel target.
    3.  Ripeti per i vicini, senza mai tornare indietro.
*   **Rischio:** Può bloccarsi in minimi locali (soluzioni sbagliate), ma per grafi piccoli spesso funziona bene.

#### C. Beam Search
Una via di mezzo tra Greedy e Backtracking.
*   **Come funziona:** Mentre costruisci l'albero di ricerca, invece di esplorare *tutto*, tieni in memoria solo le migliori $K$ soluzioni parziali a ogni livello.

---

### 3. Metodi basati su AI / Embedding (Learning)
Modi moderni, ma probabilmente "overkill" (eccessivi) per il tuo caso.

#### A. Graph Neural Networks (GNN) - Siamese Networks
*   **Come funziona:** Addestri una rete neurale per convertire ogni grafo in un vettore (embedding). La somiglianza è il prodotto scalare tra i vettori.
*   **Pro:** Istantaneo dopo il training.
*   **Contro:** Non ti dà la *mappatura* (quale nodo corrisponde a quale), ti dà solo uno score globale.

---

### Quale dovresti scegliere?

Data la tua distribuzione dei dati (99% dei casi $N \le 4$, rari casi $N \ge 7$):

1.  **La Scelta Migliore (Bilanciata): Backtracking Ottimizzato.**
    Usa l'algoritmo che ti ho scritto nella risposta precedente (iterare sui nodi, derivare gli archi). È un approccio **Esatto (Branch & Bound)** semplificato. Dato che $7! = 5040$, è gestibilissimo in Python se eviti il ciclo interno sugli archi.

2.  **La Scelta Scalabile: Algoritmo Ungherese (`scipy`).**
    Se noti che i casi con $N=8,9$ sono troppo lenti, implementa una fallback:
    *   Se $N < 7$: Usa il tuo metodo esatto.
    *   Se $N \ge 7$: Usa `scipy.optimize.linear_sum_assignment` basandoti su una matrice di somiglianza locale (label + proprietà). Sarà istantaneo ma leggermente meno preciso.