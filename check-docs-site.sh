#!/usr/bin/env bash
# Check the Tautulli docs site. Run it after each hosting step.
#
# Usage: ./check-docs-site.sh [--no-redirects] [--no-nightly] [released-url] [nightly-url]
#
#   released-url    Default https://docs.tautulli.com
#   nightly-url     Default https://docs-nightly.tautulli.com
#   --no-redirects  Skip the _redirects rules. Use it for a host without
#                   redirect support, such as GitHub Pages.
#   --no-nightly    Skip the nightly site.
#
# A base URL can have a path, for example https://samwiseg0.github.io/Tautulli.
# Each check prints one ok, FAIL or skip line. The script exits 1 when a check
# fails. It needs only curl and a POSIX shell.
#
# Examples:
#   ./check-docs-site.sh
#   ./check-docs-site.sh --no-redirects --no-nightly https://samwiseg0.github.io/Tautulli
#   ./check-docs-site.sh http://localhost:8788 http://localhost:8789

PAGES='/ /installation /asking-for-support /debugging /frequently-asked-questions
/notification-agents-guide /custom-notification-conditions /custom-scripts
/3rd-party-apis-guide /exporter-guide /api-reference /search'

# Released Tautulli versions link to these anchors.
ANCHORS='/installation#tautulli-login /frequently-asked-questions#general-q21
/frequently-asked-questions#notifications-cryptography'

# The rules in website/static/_redirects on 2026-11-16, as "from to" pairs.
# The last pair tests the trailing-slash rule (/*/ /:splat).
# Update this list when _redirects changes.
REDIRECTS='/getting-started /installation
/getting-started/installation /installation
/getting-started/installation/install-as-a-daemon /installation
/getting-started/upgrading-to-python-3 /installation
/using-tautulli /notification-agents-guide
/using-tautulli/notification-agents-guide /notification-agents-guide
/using-tautulli/custom-notification-conditions /custom-notification-conditions
/using-tautulli/exporter-guide /exporter-guide
/using-tautulli/3rd-party-apis-guide /3rd-party-apis-guide
/support /asking-for-support
/support/asking-for-support /asking-for-support
/support/frequently-asked-questions /frequently-asked-questions
/support/debugging /debugging
/extending-tautulli /custom-scripts
/extending-tautulli/custom-scripts /custom-scripts
/extending-tautulli/api-reference /api-reference
/support/debugging/ /support/debugging'

MARKER='name="generator" content="Docusaurus'
NOINDEX='name="robots" content="noindex'

redirects=1 nightly=1 released='' nightly_url=''
for arg; do
  case $arg in
    --no-redirects) redirects=0 ;;
    --no-nightly) nightly=0 ;;
    -*) echo "Usage: $0 [--no-redirects] [--no-nightly] [released-url] [nightly-url]" >&2; exit 2 ;;
    *) if [ -z "$released" ]; then released=$arg; else nightly_url=$arg; fi ;;
  esac
done
released=${released:-https://docs.tautulli.com}
released=${released%/}
nightly_url=${nightly_url:-https://docs-nightly.tautulli.com}
nightly_url=${nightly_url%/}

passed=0 failed=0 skipped=0
ok() { passed=$((passed + 1)); printf 'ok    %s\n' "$1"; }
bad() { failed=$((failed + 1)); printf 'FAIL  %s: %s\n' "$1" "$2"; }
skip() { skipped=$((skipped + 1)); printf 'skip  %s: %s\n' "$1" "$2"; }

# get URL [body]: sets code, loc (the redirect target) and err. With "body",
# it also sets body. Returns 1 when curl fails, for example on a bad certificate.
get() {
  if [ "$2" = body ]; then
    out=$(curl -sS --max-time 30 -w '\n@@%{http_code} %{redirect_url}' "$1" 2>&1)
  else
    out=$(curl -sS --max-time 30 -o /dev/null -w '\n@@%{http_code} %{redirect_url}' "$1" 2>&1)
  fi
  rc=$?
  body=${out%@@*}
  meta=${out##*@@}
  code=${meta%% *}
  loc=${meta#* }
  err="HTTP $code${loc:+ to $loc}"
  if [ $rc -ne 0 ]; then
    err=${out##*curl: }
    err="curl: ${err%%"$nl"*}"
    return 1
  fi
}
nl='
'

# want200 LABEL URL: one check that URL answers 200.
want200() {
  if get "$2" && [ "$code" = 200 ]; then ok "$1"; else bad "$1" "$err"; fi
}

check_site() {
  name=$1 base=$2

  # A DNS, connection or certificate error fails every request. Report it once.
  if ! get "$base/"; then
    bad "$name site reachable" "$err"
    return 1
  fi

  for p in $PAGES; do
    if ! get "$base$p" body || [ "$code" != 200 ]; then
      bad "$name page $p" "$err"
      continue
    fi
    case $body in
      *"$MARKER"*) ok "$name page $p" ;;
      *) bad "$name page $p" "still the old site, no Docusaurus generator tag" ;;
    esac
  done

  for a in $ANCHORS; do
    if ! get "$base${a%%#*}" body || [ "$code" != 200 ]; then
      bad "$name anchor $a" "$err"
      continue
    fi
    case $body in
      *"id=\"${a#*#}\""*) ok "$name anchor $a" ;;
      *) bad "$name anchor $a" "no id=\"${a#*#}\" in the page" ;;
    esac
  done

  # The home page names the hashed main and runtime scripts.
  get "$base/" body
  home=$body
  case $home in
    *'/assets/js/main.'*)
      js=${home#*/assets/js/main.}
      want200 "$name hashed asset main.${js%%\"*}" "$base/assets/js/main.${js%%\"*}"
      ;;
    *) bad "$name hashed asset" "no assets/js/main.<hash>.js in the home page" ;;
  esac
  want200 "$name logo" "$base/img/logo.svg"
  check_search_index

  if get "$base/check-docs-site-no-such-page" && [ "$code" = 404 ]; then
    ok "$name missing page returns 404"
  else
    bad "$name missing page returns 404" "$err"
  fi

  if [ $redirects = 1 ]; then
    while read -r from to; do
      if get "$base$from" && [ "$code" = 301 ] && [ "$loc" = "$base$to" ]; then
        ok "$name redirect $from"
      else
        bad "$name redirect $from" "want 301 to $to, got $err"
      fi
    done <<EOF
$REDIRECTS
EOF
  else
    skip "$name redirects" "--no-redirects"
  fi

  case $base in
    https://*)
      host=${base#https://}
      host=${host%%/*}
      if get "http://${base#https://}/" && { [ "$code" = 301 ] || [ "$code" = 308 ]; } &&
        case $loc in "https://$host/"*) true ;; *) false ;; esac; then
        ok "$name http redirects to https"
      else
        bad "$name http redirects to https" "$err"
      fi
      if get "https://$host/"; then ok "$name certificate valid for $host"; else bad "$name certificate valid for $host" "$err"; fi
      ;;
    *) skip "$name https" "the base URL is not https" ;;
  esac
}

# The search index has a hashed name that only a JS chunk knows. The runtime
# script maps chunk ids to file names. Fetch the chunks until one names the index.
check_search_index() {
  case $home in
    *'/assets/js/runtime~main.'*) ;;
    *) bad "$name search index" "no assets/js/runtime~main.<hash>.js in the home page"; return ;;
  esac
  rt=${home#*/assets/js/runtime~main.}
  if ! get "$base/assets/js/runtime~main.${rt%%\"*}" body; then
    bad "$name search index" "runtime script: $err"
    return
  fi
  # The runtime builds "assets/js/" + ({id:"name"}[e]||e) + "." + {id:"hash"}[e] + ".js".
  rest=${body#*\"assets/js/\"+}
  names=
  case $rest in "({"*) names=${rest#??}; names=${names%%\}*} ;; esac
  rest=${rest#*\".\"+\{}
  hashes=${rest%%\}*}
  index=
  ifs=$IFS
  IFS=,
  for pair in $hashes; do
    IFS=$ifs
    id=${pair%%:*}
    file=${pair#*:\"}
    file=${file%\"}
    case ",$names" in
      *",$id:\""*) n=",$names"; n=${n#*",$id:\""}; file="${n%%\"*}.$file" ;;
      *) file="$id.$file" ;;
    esac
    get "$base/assets/js/$file.js" body || continue
    case $body in
      *'search-index{dir}-'*)
        index=${body#*search-index\{dir\}-}
        index="search-index-${index%%.json*}.json"
        break
        ;;
    esac
  done
  IFS=$ifs
  if [ -n "$index" ]; then
    want200 "$name search index $index" "$base/$index"
  else
    bad "$name search index" "no JS chunk names a search-index file"
  fi
}

check_released() {
  get "$released/" body
  case $body in
    *"$NOINDEX"*) bad "released indexable" "the home page has a noindex robots meta" ;;
    *) ok "released indexable" ;;
  esac
  case $body in
    *theme-announcement-bar*) bad "released has no notice bar" "the home page shows a notice bar" ;;
    *) ok "released has no notice bar" ;;
  esac
  if ! get "$released/sitemap.xml" body || [ "$code" != 200 ]; then
    bad "released sitemap" "$err"
    return
  fi
  case $body in
    *"<loc>$released/"*) ok "released sitemap on $released" ;;
    *"<loc>"*) loc=${body#*<loc>}; bad "released sitemap" "lists ${loc%%<*}, want $released/" ;;
    *) bad "released sitemap" "no <loc> entries" ;;
  esac
}

check_nightly() {
  get "$nightly_url/" body
  case $body in
    *"$NOINDEX"*) ok "nightly noindex" ;;
    *) bad "nightly noindex" "no noindex robots meta in the home page" ;;
  esac
  case $body in
    *theme-announcement-bar*) ok "nightly notice bar" ;;
    *) bad "nightly notice bar" "no notice bar in the home page"; return ;;
  esac
  bar=${body#*theme-announcement-bar}
  bar=${bar%%</div>*}
  case $bar in
    *href=*) ;;
    *) bad "nightly notice bar links to $released" "the bar has no link"; return ;;
  esac
  href=${bar#*href=\"}
  href=${href%%\"*}
  if [ "${href%/}" = "$released" ]; then
    ok "nightly notice bar links to $released"
  else
    bad "nightly notice bar links to $released" "it links to $href"
  fi
}

echo "Released site: $released"
check_site released "$released" && check_released
echo
if [ $nightly = 1 ]; then
  echo "Nightly site: $nightly_url"
  check_site nightly "$nightly_url" && check_nightly
else
  skip "nightly site" "--no-nightly"
fi

echo
echo "$passed ok, $failed failed, $skipped skipped"
[ $failed -eq 0 ]
