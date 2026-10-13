import re
import sys
import urllib.request as u

naam = sys.argv[1] if len(sys.argv) > 1 else "1998-2008 Extrema"
lijst = u.urlopen("http://127.0.0.1:5077/review?filter=alle").read().decode()
m = re.search(r"/review/([0-9a-f]+)[^>]*>" + re.escape(naam), lijst)
d = u.urlopen("http://127.0.0.1:5077/review/" + m.group(1)).read().decode()
i = d.find("Jaar en plek:")
t = re.sub(r'<a href="([^"]+)"[^>]*>[^<]*</a>', r"[\1]", d[i:i + 3000])
print(re.sub(r"<[^>]+>", "", t)[:1500])
