from detect import bounds_from_words
def mk(text, t0, dt=0.4):
    return [{"word": w, "start": t0+i*dt, "end": t0+i*dt+0.3} for i, w in enumerate(text.split())]
sermon = mk("today we talk about grace " * 80, 100)           # ~ 100-260s
w = (mk("The Gospel of Christ praise and honour to you lord jesus christ", 50)   # earlier sung response (misheard)
     + mk("praise and honor to you Lord Jesus Christ", 90)                       # the song
     + sermon
     + mk("church of jesus christ what gifts have you brought for your lord", 400)
     + mk("praise and honor to you lord jesus christ", 500))                      # after: must be ignored
print(bounds_from_words(w, 600))   # expect ~ (93.6, ~399.7)
try: bounds_from_words(sermon, 600)
except RuntimeError as e: print("ok raises:", e)

# song sung twice back-to-back: start must land after the second
w2 = (mk("praise and honor to you lord jesus christ", 90) + mk("praise and honor to you lord jesus christ", 96)
      + sermon + mk("church of jesus christ what gifts have you brought for your lord", 400))
st, en = bounds_from_words(w2, 600); assert 99 < st < 100, st
# echoed end phrase before the song must be ignored
w3 = mk("church of jesus christ what gifts have you brought for your lord", 5) + w2
st, en = bounds_from_words(w3, 600); assert en > 399, en
print("PASS")
