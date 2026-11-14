#!/bin/bash
# Keyrir allar mælingar einnar lotu í röð, í bakgrunni (nohup), og ræsir
# vefþjón á gátt 8000 svo hægt sé að sækja gögnin á http://<vél>:8000/data/
#
#   ./lota.sh 1    jafnvægismæling: fan_test + step1_equilibrium      (~40 mín)
#   ./lota.sh kort kyrrstöðuferill T(u): 50,20,35,50,65,80,50 %, 5,5 mín hvert (~40 mín);
#                  50 % þrisvar til að greina hægt rek (upphitun kassa, herbergishita)
#   ./lota.sh 2    liður 1 v1, liður 1 v2, liður 2 v1                  (~39 mín)
#   ./lota.sh 3    liður 2 v2, liður 3 v1                              (~38 mín)
#   ./lota.sh 4    liður 3 v2                                          (~19 mín)
#
# Lotur á Pi tölvunum eru heilir tímar (t.d. 11:00-12:00) og notandinn er
# skráður út á heila tímanum. Skriftan neitar að byrja ef mælingarnar ná ekki
# að klárast fyrir þann tíma (svo hitagjafinn sé aldrei skilinn eftir í gangi).
# --force sleppir þeirri athugun, --sim notar hermi.
#
# Fylgjast með:  tail -n +1 -f lotaN.log      Stöðva:  ./lota.sh stop
cd "$(dirname "$0")" || exit 1

LOTA="$1"; shift
SIM=""; FORCE=""
for a in "$@"; do
  case "$a" in
    --sim) SIM="--sim" ;;
    --force) FORCE=1 ;;
  esac
done

if [ "$LOTA" = "stop" ]; then
  echo "Stöðva mælingar (hitagjafinn slokknar og viftan kælir)..."
  pkill -INT -f "lota_keyrsla" ; pkill -INT -f "run_part|step1_equilibrium|fan_test"
  exit 0
fi

DATA=../data; [ -n "$SIM" ] && DATA=../data_sim

case "$LOTA" in
  1) MIN=41; CMDS="python3 -u fan_test.py $SIM && python3 -u step1_equilibrium.py --min-time 240 --max-time 750 $SIM" ;;
  kort) MIN=41; CMDS="python3 -u step1_equilibrium.py --levels 50 20 35 50 65 80 50 --min-time 300 --max-time 330 --out $DATA/step1_kort.csv $SIM" ;;
  2) MIN=40; CMDS="python3 -u run_part1.py v1 $SIM && python3 -u run_part1.py v2 $SIM && python3 -u run_part2.py v1 $SIM" ;;
  3) MIN=39; CMDS="python3 -u run_part2.py v2 $SIM && python3 -u run_part3.py v1 $SIM" ;;
  4) MIN=20; CMDS="python3 -u run_part3.py v2 $SIM" ;;
  *) echo "Notkun: ./lota.sh 1|kort|2|3|4 [--sim] [--force]   eða   ./lota.sh stop"; exit 1 ;;
esac

# Er eitthvað þegar í gangi?
if pgrep -f "run_part|step1_equilibrium|fan_test" >/dev/null; then
  echo "VILLA: mæling er þegar í gangi:"; pgrep -af "run_part|step1_equilibrium|fan_test"; exit 1
fi

# Þarf líkan fyrir liði 1-3
if [ "$LOTA" != "1" ] && [ "$LOTA" != "kort" ] && [ ! -f "$DATA/model.json" ]; then
  echo "VILLA: $DATA/model.json vantar. Það verður til úr jafnvægismælingunni (lota 1)."
  exit 1
fi

# Nær lotan að klárast fyrir heila tímann?
LEFT=$(( 60 - 10#$(date +%M) ))
if [ -z "$FORCE" ] && [ -z "$SIM" ] && [ "$LEFT" -lt $((MIN + 2)) ]; then
  echo "VILLA: lota $LOTA tekur allt að $MIN mín en aðeins $LEFT mín eru eftir af tímanum."
  echo "Byrjið í upphafi næstu lotu (eða notið --force ef lotan endar ekki á heila tímanum)."
  exit 1
fi

# Vefþjónn fyrir gögnin
if ! pgrep -f "http.server 8000" >/dev/null; then
  nohup python3 -m http.server 8000 --directory .. >/dev/null 2>&1 &
fi

LOG="lota$LOTA.log"
nohup bash -c "exec -a lota_keyrsla bash -c '$CMDS; echo; echo \"=== LOTU $LOTA LOKIÐ \$(date +%H:%M) ===\"'" > "$LOG" 2>&1 &
sleep 1
echo "Lota $LOTA hafin kl. $(date +%H:%M), tekur allt að $MIN mín."
echo "Fylgjast með:   tail -n +1 -f $LOG     (Ctrl+C hættir að fylgjast með, mælingin heldur áfram)"
echo "Stöðva:         ./lota.sh stop"
echo "Gögn:           http://$(hostname -f 2>/dev/null || hostname):8000/data/"
