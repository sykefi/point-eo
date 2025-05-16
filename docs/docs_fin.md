Rasterien tulkinta pisteaineiston avulla point-eo -kirjastolla

# Yleisiä ohjeita
Avaa VS Code:
E:\vscode\Microsoft VS Code -> Code.exe
Voi olla hyvä ajatus tehdä tästä shortcut työpöydälle

Päivitä repositorio silloin tällöin:
    Avaa Git-versionhallinta:
        C:\Program Files\Git -> git-bash.exe
        voi olla myös käynnistysvalikossa
    Aja komennot git bash -ikkunassa:
        $ cd e:
        $ cd mikkoi/point-eo
        $ git pull

Jos komentorivi ilmoittaa "Already up to date", kaikki on ajan tasalla.

Käynnistä conda-ympäristö:
    Avaa "Anaconda prompt (anaconda3)" Windowsin käynnistysvalikosta
    Listaa kaikki ympäristöt:
        $ conda env list
    Aktivoi ympäristö:
        $ conda activate point-eo

Luo uusi conda-ympäristö tiedostosta:
Koneelle on asennettu mamba-paketti (base)-ympäristöön.
Se löytää pakettien yhteensopivuudet condan oletus-solveria huomattavasti nopeammin.
Käyttö tapahtuu korvaamalla 'conda'-osat komennoista komennolla 'mamba'
esim.

$ mamba env create -f environment.yml

Conda-ympäristön poisto:

$ conda env remove -n ENV_NAME

## 01. Random Forest mallin evaluointi datasetillä ja opetuspisteillä

Koealojen sarakkeet saa esim komennolla:
ogrinfo E:\Inputs\reference\koealat_20_22_220222_b10m_9feas_cl.shp -ro -al -nomd

1. Poimitaan lähtödatasta koealapisteiden perusteella taulukko:

point-eo sample_raster ^
    --input data\\pointEO_testdata\\points_clc.geojson ^
    --input_raster data\\pointEO_testdata\\s2_2018_lataseno.tif ^
    --target corine ^
    --out_folder testi\\demo\\suot

1b. Jos halutaan lisätä kanavien nimet, se tehdään listaamalla ne erillisessä tiedostossa joka annetaan parametrina
    --band_names bandnames.txt ^
jokainen bandname omalla rivillä.

Parametri `--rename_target NIMI` vaihtaa target-muuttujan sarakkeen tarvittaessa, jos muuttujalla on sama nimi kuin kanavilla.

Geometriat tallentuvat oletuksena geojson-modossa. Parametrilla `--shp` ulostulo tallentuu shapefilena.

Nyt taulukko on tiedostossa
sampling\\s2_2018_lataseno__points_clc__corine.tif

2. Ajetaan random-forest koulutus ja analyysi tälle taulukolle

point-eo analysis ^
    --input sampling\\s2_2018_lataseno__points_clc__corine.csv ^
    --out_prefix demo_rf ^
    --out_folder models\\demo_rf ^
    --separator , ^
    --decimal . ^
    --remove_classes_smaller_than 6

Mallin tarkkuusmetriikat ja muut tiedot tulostetaan komentoriville ja kuvat tallennetaan tiedostoihin.
Tulostettavien kuvaajien fonttikokoja voi muuttaa parametereilla
```cmd
--confusion_matrix_fonts "22,20,20"
--classification_report_fonts "22,20,20"
```


# 02. AutoML

Automaattisen mallin etsinnän TPOT-kirjaston geneettisellä algoritmilla voi ajaa komennolla:

point-eo tpot_train ^
    --input sampling\\s2_2018_lataseno__points_clc__corine.csv ^
    --out_prefix tpot_demo ^
    --out_folder models\\tpot_demo ^
    --generations 2 ^
    --population_size 10 ^
    --scoring f1_weighted

TPOT toimii geneettisellä algoritmilla, jossa koulutetaan --population_size -parametrin mukainen määrä
malleja, joista parhaiten pärjääviä malleja yhdistetään satunnaisesti luoden uusia malleja seuraavaa 'sukupolvea'
varten. Tätä toistetaan --generations -parametrin määrittämien sukupolvien ajan.

Parametrit:
	--input: csv-tiedosto, jossa kohdeluokka ensimmäisessä sarakkeessa ja piirteet seuraavissa
	--output: ulostulon etuliite
	--generations: sukupolvien määrä, montako kertaa optimointia iteroidaan
	--population_size: populaation koko, montako mallia opetetaan kerralla
	--scoring: metriikka jota optimoidaan. f1_weighted on hyvä lähtökohta epätasaisella luokkajaolla

Malli tallentuu tiedostoon jonka etuliitteenä on --output -argumentin teksti.

## AutoML-mallin analyysi

Kun halutaan tarkempia tuloksia TPOTin tuottamasta mallista, voidaan ajaa sama rf_analysis.py -skripti taulukkodatalle
antamalla yhdeksi parametriksi edellisen TPOT-skriptin tuottama mallitiedosto

point-eo analysis ^
    --input sampling\\s2_2018_lataseno__points_clc__corine.csv ^
    --out_prefix tpot_demo ^
    --out_folder tpot_analysis ^
    --tpot_model models\\tpot_demo\\tpot_demo_acc0.6362_230606T133630.py  ^
    --separator , ^
    --decimal . ^
    --remove_classes_smaller_than 6

# 03. tulkinta

Tulkinta suoritetaan `predict`-komennolla ja siihen tarvitaan malli, joka on tallennettu `analysis`-skriptillä .pkl-muodossa

point-eo predict ^
    --model models\\demo_rf\\demo_rf__s2_2018_lataseno__points_clc__corine__2023-06-06T15-16-10_model.pkl ^
    --input_raster data\\pointEO_testdata\\s2_2018_lataseno.tif ^
    --cell_size 1000 ^
    --cell_buffer 1 ^
    --extent data\\pointEO_testdata\\testarea_lataseno\\testarea_lataseno.shp ^
    --out_folder predictions\\demo_tulkinta


--cell_size -parametri kertoo kuinka suuria alueita käsitellään kerrallaan muistissa (cell_size X cell_size pikseliä). 
Jos muisti ei riitä, pienennä tätä arvoa. Kannattaa käytää suurinta mahdollista arvoa joka muistiin mahtuu. 
--cell_buffer -parametri määrittää kuinka paljon kutakin ruutua bufferoidaan. Varmuuden vuoksi 1, mutta pitäisi toimia myös 0:lla [mikkoi 14.9.23: Oli ennen nimellä 'block_buffer']


Virtuaalirasteri voidaan muuttaa normaaliksi rasteriksi GDALin avulla:
Etsi gdal_merge.py: where gdal_merge.py

python E:\\anaconda\\anaconda3\\envs\\point-eo\\Scripts\\gdal_merge.py ^
-o predictions\\demo_tulkinta\\demo_C.tif ^
-co "COMPRESS=LZW" ^
-co "BIGTIFF=YES" ^
-co "TILED=YES" ^
-ot "UInt16" ^
predictions\\demo_tulkinta\\s2_2018_lataseno__demo_rf__s2_2018_lataseno__points_clc__corine__2023-06-06T15-16-10_model_C.vrt


Rasterin kanavat voidaan nimetä uudelleen tiedostosta, joka on luotu `analysis`-skriptillä
point-eo set_band_description ^
    --input_raster predictions\\demo_tulkinta\\demo_C.tif ^
    --label_map models\\demo_rf\\demo_rf__s2_2018_lataseno__points_clc__corine__2023-06-06T13-34-57_label_map.txt


Lopuksi voidaan luoda rasteri jossa vain todennäköisin luokka, sekä maksimitodennäköisyyden arvo
point-eo postprocess_prediction ^
    --input_raster predictions\\demo_tulkinta\\demo_C.tif ^
    --out_folder predictions\\demo_tulkinta ^
    --label_map models\\demo_rf\\demo_rf__s2_2018_lataseno__points_clc__corine__2023-06-06T13-34-57_label_map.txt