import unicodedata
from collections import Counter
from django.core.management.base import BaseCommand
from django.db import transaction

from tienda.models import Producto


def _norm(texto):
    t = (texto or '').lower().strip()
    t = unicodedata.normalize('NFKD', t)
    return ''.join(c for c in t if not unicodedata.combining(c))


# Diccionario maestro de especies aprobadas: (keywords_normalizadas, ficha_dict)
# Ordenado de mayor especificidad a menor para evitar colisiones (ej. "garza boyera" antes de "garza").
ESPECIES_CATALOGO = [
    # --- AVES ---
    (['bandurria'], {
        'comun': 'Bandurria',
        'cientifico': 'Theristicus melanopis',
        'habitat': 'Humedales, praderas húmedas y campos abiertos desde Atacama hasta Tierra del Fuego.',
        'conservacion': 'Preocupación menor (LC)',
        'dato': 'Su canto metálico y potente anuncia su paso al amanecer y atardecer. Usa su largo pico curvo para sondear el suelo húmedo en busca de insectos, larvas y gusanos.',
    }),
    (['buho nival'], {
        'comun': 'Búho nival',
        'cientifico': 'Bubo scandiacus',
        'habitat': 'Tundra ártica del hemisferio norte (América del Norte, Europa y Asia); especie no presente en Chile.',
        'conservacion': 'Vulnerable (VU) según UICN',
        'dato': 'A diferencia de la mayoría de los búhos, es activo principalmente durante el día para aprovechar la luz continua del verano ártico. Sus plumas cubren incluso sus dedos para aislarlo del frío extremo.',
    }),
    (['cachudito'], {
        'comun': 'Cachudito',
        'cientifico': 'Anairetes parulus',
        'habitat': 'Matorrales, jardines, quebradas y bordes de bosque desde Atacama hasta Tierra del Fuego.',
        'conservacion': 'Preocupación menor (LC)',
        'dato': 'Es una de las aves más pequeñas e inquietas de Chile, fácil de reconocer por su penacho de plumas negras curvadas hacia adelante. Se mueve sin parar entre las ramas cazando diminutos insectos.',
    }),
    (['carpintero'], {
        'comun': 'Carpintero negro',
        'cientifico': 'Campephilus magellanicus',
        'habitat': "Bosques nativos maduros de Nothofagus desde O'Higgins hasta Tierra del Fuego.",
        'conservacion': 'Preocupación menor (LC)',
        'dato': 'Es el carpintero más grande de Sudamérica; el macho luce una cabeza rojo brillante y la hembra un copete negro curvado. Su doble golpe seco en los troncos resuena a gran distancia en el bosque templado.',
    }),
    (['chorlo artico'], {
        'comun': 'Chorlo ártico',
        'cientifico': 'Pluvialis squatarola',
        'habitat': 'Visitante migratorio boreal presente en playas, estuarios y humedales costeros a lo largo de todo Chile.',
        'conservacion': 'Vulnerable (VU) según UICN',
        'dato': 'Cría en la tundra ártica y recorre miles de kilómetros hasta las costas chilenas para pasar el verano austral. En plumaje reproductivo luce pecho y cara completamente negros.',
    }),
    (['chorlo ceniciento'], {
        'comun': 'Chorlo ceniciento',
        'cientifico': 'Pluvianellus socialis',
        'habitat': 'Lagunas salobres, estepas y estuarios de la Patagonia austral (Magallanes y Tierra del Fuego).',
        'conservacion': 'En peligro (EN) en Chile (RCE) / Casi amenazado (NT) UICN',
        'dato': 'Especie endémica de la Patagonia austral y única representante de su familia. A diferencia de otros chorlos, alimenta a sus pichones regurgitando alimento desde su buche.',
    }),
    (['chorlo chileno'], {
        'comun': 'Chorlo chileno',
        'cientifico': 'Charadrius modestus',
        'habitat': 'Estepas patagónicas y turberas en época reproductiva (sur de Chile); en invierno migra hacia playas y praderas húmedas hasta el norte chico.',
        'conservacion': 'Preocupación menor (LC)',
        'dato': 'Durante la primavera austral luce un pecho rufo intenso bordeado por una banda negra. En invierno forma bandadas mixtas en costas y potreros húmedos del centro y sur del país.',
    }),
    (['chorlo de campo'], {
        'comun': 'Chorlo de campo',
        'cientifico': 'Oreopholus ruficollis',
        'habitat': 'Estepas, pampas, dunas y campos abiertos desde Arica y Parinacota hasta Tierra del Fuego.',
        'conservacion': 'Preocupación menor (LC)',
        'dato': 'De postura erguida y andar veloz, confía en su plumaje mimético para pasar inadvertido entre piedras y pastizales secos. Posee una mancha negra característica en el vientre.',
    }),
    (['chorlo nevado'], {
        'comun': 'Chorlo nevado',
        'cientifico': 'Anarhynchus nivosus',
        'habitat': 'Playas arenosas, dunas costeras y salares desde Arica hasta Chiloé.',
        'conservacion': 'Vulnerable (VU) en Chile (RCE) / Casi amenazado (NT) UICN',
        'dato': 'Anida directamente sobre la arena entre conchas y algas, donde sus huevos quedan perfectamente camuflados. Es muy sensible a la presencia de perros sueltos y vehículos en las playas.',
    }),
    (['chorlo semipalmado'], {
        'comun': 'Chorlo semipalmado',
        'cientifico': 'Charadrius semipalmatus',
        'habitat': 'Visitante migratorio boreal frecuente en playas, desembocaduras y planicies mareales de todo Chile.',
        'conservacion': 'Preocupación menor (LC)',
        'dato': 'Recibe su nombre por las pequeñas membranas que unen la base de sus dedos, útiles para desplazarse sobre barro blando. Corre en tramos cortos y se detiene bruscamente para atrapar invertebrados.',
    }),
    (['choroy'], {
        'comun': 'Choroy',
        'cientifico': 'Enicognathus leptorhynchus',
        'habitat': 'Endémico de Chile; bosques templados, araucarias y campos desde Valparaíso hasta Aysén.',
        'conservacion': 'Preocupación menor (LC)',
        'dato': 'Loro endémico de Chile reconocible por su pico superior alargado y delgado, ideal para extraer piñones de araucaria y semillas. Se desplaza en bandadas ruidosas por los bosques del sur.',
    }),
    (['chucao'], {
        'comun': 'Chucao',
        'cientifico': 'Scelorchilus rubecula',
        'habitat': 'Sotobosque denso y húmedo de bosques templados desde Colchagua hasta Aysén.',
        'conservacion': 'Preocupación menor (LC)',
        'dato': 'Más fácil de escuchar que de ver, su fuerte canto resuena entre helechos y quilas del bosque valdiviano. En la tradición chilota se dice que su canto desde la derecha augura buena suerte al caminante.',
    }),
    (['chuncho'], {
        'comun': 'Chuncho',
        'cientifico': 'Glaucidium nana',
        'habitat': 'Bosques, matorrales, parques y zonas cordilleranas desde Atacama hasta Tierra del Fuego.',
        'conservacion': 'Preocupación menor (LC)',
        'dato': 'Es el búho más pequeño de Chile, pero un cazador capaz de capturar presas de su propio tamaño. En la nuca tiene dos manchas oscuras que simulan ojos para disuadir ataques por la espalda.',
    }),
    (['colegial'], {
        'comun': 'Colegial',
        'cientifico': 'Lessonia rufa',
        'habitat': 'Playas, vegas, bordes de lagunas, humedales y estepas de todo Chile.',
        'conservacion': 'Preocupación menor (LC)',
        'dato': 'El macho exhibe un manto rojo ladrillo intenso sobre su plumaje negro, mientras que la hembra es de tonos pardos discretos. Camina ágilmente por el suelo persiguiendo insectos cerca del agua.',
    }),
    (['condor'], {
        'comun': 'Cóndor andino',
        'cientifico': 'Vultur gryphus',
        'habitat': 'Cordillera de los Andes, precordillera y sectores costeros australes desde Arica hasta Magallanes.',
        'conservacion': 'Vulnerable (VU) en Chile (RCE) y UICN',
        'dato': 'Es una de las aves voladoras más grandes del mundo, con una envergadura que supera los 3 metros. Aprovecha las corrientes térmicas ascendentes para planear largas distancias casi sin batir las alas.',
    }),
    (['flamencos surire'], {
        'comun': 'Flamenco chileno',
        'cientifico': 'Phoenicopterus chilensis',
        'habitat': 'Salares altiplánicos (como el Salar de Surire), lagunas y humedales costeros a lo largo de Chile.',
        'conservacion': 'Vulnerable (VU) en Chile (RCE) / Casi amenazado (NT) UICN',
        'dato': 'Filtra microorganismos y pequeños crustáceos del agua salobre usando láminas dentro de su pico curvo. El tono rosado de su plumaje proviene directamente de los carotenoides de su dieta.',
    }),
    (['garza boyera'], {
        'comun': 'Garza boyera',
        'cientifico': 'Bubulcus ibis',
        'habitat': 'Praderas agrícolas, humedales y potreros con ganado desde Arica hasta Magallanes.',
        'conservacion': 'Preocupación menor (LC)',
        'dato': 'Suele acompañar a vacas y caballos para capturar los insectos que estos espantan al caminar por el pasto. En época reproductiva desarrolla llamativas plumas anaranjadas en la cabeza y el dorso.',
    }),
    (['garza cuca'], {
        'comun': 'Garza cuca',
        'cientifico': 'Ardea cocoi',
        'habitat': 'Humedales, ríos, estuarios, lagos y costas protegidas desde Atacama hasta Aysén.',
        'conservacion': 'Preocupación menor (LC)',
        'dato': 'Es la garza más grande de Chile, superando el metro de altura. Permanece inmóvil en aguas someras antes de lanzar su pico como un arpón sobre peces y anfibios.',
    }),
    (['gaviotin monja'], {
        'comun': 'Gaviotín monja',
        'cientifico': 'Larosterna inca',
        'habitat': 'Costas e islas rocosas de la corriente de Humboldt desde Arica hasta el centro-sur de Chile.',
        'conservacion': 'Vulnerable (VU) en Chile (RCE) / Casi amenazado (NT) UICN',
        'dato': 'Inconfundible por sus bigotes blancos curvados a ambos lados del pico rojo brillante. Se zambulle desde el aire para capturar pequeños peces pelágicos en aguas frías.',
    }),
    (['golondrina bermeja'], {
        'comun': 'Golondrina bermeja',
        'cientifico': 'Hirundo rustica',
        'habitat': 'Visitante migratorio estival en campos abiertos, humedales y pueblos a lo largo de Chile.',
        'conservacion': 'Preocupación menor (LC)',
        'dato': 'Realiza una de las migraciones más extensas entre las aves paseriformes, viajando desde Norteamérica hasta Sudamérica cada primavera austral. Su cola ahorquillada le da gran agilidad aérea.',
    }),
    (['golondrina chilena'], {
        'comun': 'Golondrina chilena',
        'cientifico': 'Tachycineta leucopyga',
        'habitat': 'Campos, humedales, pueblos y claros de bosque desde Atacama hasta Tierra del Fuego.',
        'conservacion': 'Preocupación menor (LC)',
        'dato': 'Se distingue por su dorso azul metálico brillante y una nítida mancha blanca sobre la base de la cola. Anida en cavidades de árboles, acantilados o bajo techos rurales.',
    }),
    (['guacamayo azul y amarillo'], {
        'comun': 'Guacamayo azul y amarillo',
        'cientifico': 'Ara ararauna',
        'habitat': 'Selvas húmedas y sabanas tropicales de Sudamérica (no nativo de Chile).',
        'conservacion': 'Preocupación menor (LC) según UICN',
        'dato': 'Ave muy sociable e inteligente que suele formar parejas de por vida. Su potente pico curvo le permite abrir semillas y nueces muy duras que pocos otros animales logran romper.',
    }),
    (['lechuza'], {
        'comun': 'Lechuza',
        'cientifico': 'Tyto alba',
        'habitat': 'Campos abiertos, matorrales, zonas rurales y urbanas desde Arica hasta Tierra del Fuego.',
        'conservacion': 'Preocupación menor (LC)',
        'dato': 'Su disco facial en forma de corazón canaliza el menor sonido hacia sus oídos asimétricos. Gracias a ello y a su vuelo silencioso, puede cazar roedores en oscuridad casi total.',
    }),
    (['loica'], {
        'comun': 'Loica',
        'cientifico': 'Leistes loyca',
        'habitat': 'Praderas, matorrales, terrenos agrícolas y estepas desde Atacama hasta Tierra del Fuego.',
        'conservacion': 'Preocupación menor (LC)',
        'dato': 'El macho destaca por su pecho rojo escarlata intenso, visible a distancia cuando canta posado sobre cercos o arbustos. Es una excelente aliada del campo al consumir gran cantidad de insectos.',
    }),
    (['martin pescador', 'martin chico', 'martin grande'], {
        'comun': 'Martín pescador',
        'cientifico': 'Megaceryle torquata',
        'habitat': 'Ríos, lagos, estuarios y fiordos desde el centro-sur hasta Tierra del Fuego.',
        'conservacion': 'Preocupación menor (LC)',
        'dato': 'Se lanza en picada vertical desde una percha alta para atrapar peces bajo la superficie del agua. Anida excavando largos túneles horizontales en barrancos de tierra junto a los ríos.',
    }),
    (['nuco'], {
        'comun': 'Nuco',
        'cientifico': 'Asio flammeus',
        'habitat': 'Humedales, vegas, pastizales y estepas desde Tarapacá hasta Tierra del Fuego.',
        'conservacion': 'Preocupación menor (LC)',
        'dato': 'A diferencia de otras rapaces nocturnas, es frecuente verlo cazar al atardecer o en días nublados volando bajo sobre pajonales. Anida directamente en el suelo oculto entre pastos altos.',
    }),
    (['pato cortacorrientes'], {
        'comun': 'Pato cortacorrientes',
        'cientifico': 'Merganetta armata',
        'habitat': 'Ríos torrentosos y cascadas cordilleranas desde Arica hasta Tierra del Fuego.',
        'conservacion': 'Preocupación menor (LC)',
        'dato': 'Adaptado para nadar contra corrientes impetuosas y trepar rocas en ríos de montaña. El macho luce cabeza blanca con rayas negras y la hembra pecho rufo.',
    }),
    (['pato gargantillo'], {
        'comun': 'Pato gargantillo',
        'cientifico': 'Anas bahamensis',
        'habitat': 'Humedales costeros, estuarios y lagunas salobres desde Arica hasta Los Lagos.',
        'conservacion': 'Preocupación menor (LC)',
        'dato': 'Fácil de identificar por su garganta y mejillas blancas que contrastan con su pico gris azulado y base roja. Se alimenta sumergiendo la cabeza en aguas bajas.',
    }),
    (['pequen'], {
        'comun': 'Pequén',
        'cientifico': 'Athene cunicularia',
        'habitat': 'Estepas, terrenos áridos, dunas y praderas abiertas desde Arica hasta la Patagonia.',
        'conservacion': 'Preocupación menor (LC)',
        'dato': 'Pequeño búho de hábitos diurnos que suele posarse erguido sobre postes o montículos vigilando el entorno. Vive y anida en madrigueras subterráneas.',
    }),
    (['pilpilen comun'], {
        'comun': 'Pilpilén común',
        'cientifico': 'Haematopus palliatus',
        'habitat': 'Playas arenosas, desembocaduras y roqueríos costeros desde Arica hasta Chiloé.',
        'conservacion': 'Casi amenazado (NT) en Chile (RCE) / Preocupación menor (LC) UICN',
        'dato': 'Su largo pico rojo anaranjado funciona como un cincel para abrir bivalvos como machas y choritos. Anida directamente en la arena alta de las playas.',
    }),
    (['pinguino de humboldt'], {
        'comun': 'Pingüino de Humboldt',
        'cientifico': 'Spheniscus humboldti',
        'habitat': 'Costas e islas de la corriente de Humboldt desde Arica hasta Chiloé.',
        'conservacion': 'Vulnerable (VU) en Chile (RCE) y UICN',
        'dato': 'Nadador ágil que supera los 30 km/h bajo el agua usando sus aletas como remos. Posee manchas negras únicas en el pecho que permiten identificar a cada individuo.',
    }),
    (['pinguino de magallanes'], {
        'comun': 'Pingüino de Magallanes',
        'cientifico': 'Spheniscus magellanicus',
        'habitat': 'Costas e islas del sur y Patagonia de Chile (como Isla Magdalena en el Estrecho de Magallanes).',
        'conservacion': 'Preocupación menor (LC)',
        'dato': 'Se distingue por las dos bandas negras paralelas en su pecho y cuello. Cada primavera regresa fielmente a las mismas colonias para excavar madrigueras e incubar sus huevos.',
    }),
    (['pinguino rey'], {
        'comun': 'Pingüino rey',
        'cientifico': 'Aptenodytes patagonicus',
        'habitat': 'Islas subantárticas y Bahía Inútil en Tierra del Fuego.',
        'conservacion': 'En peligro (EN) en Chile (RCE) / Preocupación menor (LC) global UICN',
        'dato': 'Segundo pingüino más grande del mundo, reconocible por las manchas anaranjadas en cuello y cabeza. Incuba su único huevo manteniéndolo sobre sus patas bajo un pliegue de piel tibio.',
    }),
    (['playero de baird'], {
        'comun': 'Playero de Baird',
        'cientifico': 'Calidris bairdii',
        'habitat': 'Visitante migratorio boreal presente en playas, estuarios y lagunas altoandinas de todo Chile.',
        'conservacion': 'Preocupación menor (LC)',
        'dato': 'Cría en la tundra ártica y viaja miles de kilómetros hasta costas y salares de Sudamérica, llegando incluso sobre los 4.000 metros en los Andes.',
    }),
    (['llavero madera rara'], {
        'comun': 'Rara',
        'cientifico': 'Phytotoma rara',
        'habitat': 'Matorrales, huertos, bordes de bosque y parques desde Atacama hasta Aysén.',
        'conservacion': 'Preocupación menor (LC)',
        'dato': '¡El ave que da nombre a nuestra tienda! Su canto áspero suena como una matraca y es una de las pocas aves paseriformes casi estrictamente herbívoras gracias al borde aserrado de su pico.',
    }),
    (['siete colores'], {
        'comun': 'Siete colores',
        'cientifico': 'Tachuris rubrigastra',
        'habitat': 'Totorales y juncales de humedales, lagos y lagunas desde Atacama hasta Aysén.',
        'conservacion': 'Preocupación menor (LC)',
        'dato': 'Considerada una de las aves más coloridas de Chile, reúne tonos verdes, amarillos, azules, blancos, negros y rojos en menos de 11 cm. Construye un diminuto nido tejido entre juncos.',
    }),
    (['tortola'], {
        'comun': 'Tórtola',
        'cientifico': 'Zenaida auriculata',
        'habitat': 'Campos, matorrales, parques y ciudades a lo largo de todo Chile.',
        'conservacion': 'Preocupación menor (LC)',
        'dato': 'Su canto suave y repetitivo forma parte del paisaje sonoro de plazas y campos chilenos. Alimenta a sus pichones durante los primeros días con "leche de buche" producida por ambos padres.',
    }),
    (['treile'], {
        'comun': 'Treile / Queltehue',
        'cientifico': 'Vanellus chilensis',
        'habitat': 'Praderas, humedales, parques y estepas desde Atacama hasta Tierra del Fuego.',
        'conservacion': 'Preocupación menor (LC)',
        'dato': 'Llamado queltehue en el centro y treile en el sur, es famoso por su carácter territorial al defender su nido en el suelo. Posee espolones rojizos en el doblez de las alas.',
    }),
    (['tucuquere'], {
        'comun': 'Tucúquere',
        'cientifico': 'Bubo magellanicus',
        'habitat': 'Bosques, quebradas, estepas y cordillera desde Arica hasta Tierra del Fuego.',
        'conservacion': 'Preocupación menor (LC)',
        'dato': 'Es el búho más grande de Chile, reconocible por sus penachos de plumas y sus intensos ojos amarillos. Su grave ulular nocturno resuena a kilómetros en quebradas y bosques.',
    }),
    (['zorzal'], {
        'comun': 'Zorzal',
        'cientifico': 'Turdus falcklandii',
        'habitat': 'Bosques, matorrales, parques y jardines urbanos desde Atacama hasta Tierra del Fuego.',
        'conservacion': 'Preocupación menor (LC)',
        'dato': 'Uno de los cantores más familiares de Chile, especialmente activo al amanecer y tras la lluvia. Corre en tramos breves sobre el pasto e inclina la cabeza para detectar lombrices.',
    }),
    (['black-capped chickadee'], {
        'comun': 'Carbonero cabecinegro',
        'cientifico': 'Poecile atricapillus',
        'habitat': 'Bosques caducifolios, mixtos y parques de América del Norte (no nativo de Chile).',
        'conservacion': 'Preocupación menor (LC) según UICN',
        'dato': 'Ave curiosa y acróbata famosa por su capucha negra y su capacidad de memorizar miles de escondites donde guarda semillas para sobrevivir al invierno boreal.',
    }),
    (['eastern bluebird'], {
        'comun': 'Azulejo oriental',
        'cientifico': 'Sialia sialis',
        'habitat': 'Praderas abiertas, bordes de bosque y huertos del este de América del Norte (no nativo de Chile).',
        'conservacion': 'Preocupación menor (LC) según UICN',
        'dato': 'El macho luce un intenso dorso azul cobalto y pecho rojizo. Suele anidar en cavidades naturales de árboles y cajas anideras instaladas en campos y jardines.',
    }),

    # --- MAMÍFEROS ---
    (['chungungo'], {
        'comun': 'Chungungo',
        'cientifico': 'Lontra felina',
        'habitat': 'Costas rocosas expuestas al oleaje desde el extremo norte hasta Tierra del Fuego.',
        'conservacion': 'En peligro (EN) en Chile (RCE) y UICN',
        'dato': 'Es la nutria marina más pequeña del mundo y vive casi exclusivamente en el mar entre roqueríos y rompientes. Descansa y protege a sus crías en grietas costeras llamadas "chungungueras".',
    }),
    (['guanaco'], {
        'comun': 'Guanaco',
        'cientifico': 'Lama guanicoe',
        'habitat': 'Altiplano, estepas patagónicas, precordillera y zonas áridas desde Arica hasta Tierra del Fuego.',
        'conservacion': 'Preocupación menor (LC) / Vulnerable (VU) en sectores del norte-centro (RCE)',
        'dato': 'Es el camélido silvestre más grande de Sudamérica y antecesor de la llama doméstica. Puede correr a más de 55 km/h y habitar sobre los 4.000 metros de altura.',
    }),
    (['guina'], {
        'comun': 'Güiña',
        'cientifico': 'Leopardus guigna',
        'habitat': 'Bosques templados nativos y matorrales densos desde Coquimbo hasta Aysén.',
        'conservacion': 'Vulnerable (VU) en Chile (RCE) y UICN',
        'dato': 'Es el felino silvestre más pequeño de América, con apenas 1,5 a 3 kilos de peso. Excelente trepadora gracias a sus garras y cola gruesa, se mueve con sigilo por las copas del bosque nativo.',
    }),
    (['huemul'], {
        'comun': 'Huemul',
        'cientifico': 'Hippocamelus bisulcus',
        'habitat': 'Bosques andinos y matorrales subantárticos del sur de Chile (Ñuble, Aysén y Magallanes).',
        'conservacion': 'En peligro (EN) en Chile (RCE) y UICN',
        'dato': 'Ciervo endémico de los Andes australes y emblema nacional de Chile. Está adaptado a laderas escarpadas y nieve, desplazándose entre bosques de lenga y ñirre durante todo el año.',
    }),
    (['monito del monte'], {
        'comun': 'Monito del monte',
        'cientifico': 'Dromiciops gliroides',
        'habitat': 'Bosques templados húmedos con quila desde el Maule hasta Chiloé y Palena.',
        'conservacion': 'Casi amenazado (NT) en Chile (RCE) y UICN',
        'dato': 'Marsupial endémico de los bosques australes, más emparentado con los marsupiales australianos que con las zarigüeyas americanas. Acumula grasa en su cola y entra en letargo durante el invierno.',
    }),
    (['pudu'], {
        'comun': 'Pudú',
        'cientifico': 'Pudu puda',
        'habitat': 'Sotobosque denso de los bosques templados desde el Maule hasta Aysén (abundante en Chiloé).',
        'conservacion': 'Vulnerable (VU) en Chile (RCE) / Casi amenazado (NT) UICN',
        'dato': 'Uno de los ciervos más pequeños del mundo, alcanzando unos 40 cm de altura al hombro. Su tamaño compacto y astas cortas le permiten moverse ágilmente entre quilas y helechos espesos.',
    }),
    (['puma'], {
        'comun': 'Puma',
        'cientifico': 'Puma concolor',
        'habitat': 'Cordilleras, desiertos, bosques y estepas a lo largo de todo Chile.',
        'conservacion': 'Casi amenazado (NT) en Chile (RCE) / Preocupación menor (LC) global UICN',
        'dato': 'Es el felino más grande de Chile. Aunque es capaz de dar saltos de más de 5 metros, no puede rugir como los leones sino que emite maullidos y silbidos.',
    }),
    (['zorro chilote'], {
        'comun': 'Zorro chilote',
        'cientifico': 'Lycalopex fulvipes',
        'habitat': 'Endémico de Chile; bosques templados costeros de Nahuelbuta, Los Ríos/Los Lagos y Chiloé.',
        'conservacion': 'En peligro (EN) en Chile (RCE) y UICN',
        'dato': 'Descubierto por Charles Darwin en Chiloé en 1834, es el cánido más amenazado de Chile. Más pequeño y oscuro que otros zorros, cumple un rol clave dispersando semillas en el bosque nativo.',
    }),
    (['zorro culpeo'], {
        'comun': 'Zorro culpeo',
        'cientifico': 'Lycalopex culpaeus',
        'habitat': 'Cordilleras, valles, matorrales, desiertos y estepas desde Arica hasta Tierra del Fuego.',
        'conservacion': 'Preocupación menor (LC)',
        'dato': 'Es el zorro más grande de Chile y el segundo cánido más grande de Sudamérica. Se reconoce por sus patas y orejas rojizas y su cola larga y tupida con la punta negra.',
    }),

    # --- HONGOS ---
    (['amanita muscaria'], {
        'comun': 'Amanita muscaria',
        'cientifico': 'Amanita muscaria',
        'habitat': 'Especie introducida en Chile, asociada a plantaciones de pino (Pinus radiata) y abedules en el centro y sur.',
        'conservacion': 'Especie introducida / No evaluado (NE)',
        'dato': 'Inconfundible por su sombrero rojo brillante con verrugas blancas, forma micorrizas con las raíces de pinos exóticos. Aunque es icónica en ilustraciones, contiene compuestos tóxicos y no es comestible.',
    }),
    (['coprinus comatus'], {
        'comun': 'Barbuda',
        'cientifico': 'Coprinus comatus',
        'habitat': 'Praderas húmedas, jardines y bordes de caminos en el centro y sur de Chile.',
        'conservacion': 'No evaluado (NE)',
        'dato': 'Conocido como "hongo barbuda", tiene un sombrero cilíndrico blanco cubierto de escamas. Al madurar, sus láminas se transforman en un líquido negro similar a la tinta para liberar sus esporas.',
    }),
    (['cortinarius magellanicus'], {
        'comun': 'Cortinario azul',
        'cientifico': 'Cortinarius magellanicus',
        'habitat': 'Bosques templados nativos de Nothofagus (coigüe, lenga, ñirre) en el sur de Chile y Patagonia.',
        'conservacion': 'Preocupación menor (LC) según RCE Chile / UICN',
        'dato': 'Destaca por su intenso color violeta azulado y su superficie brillante y gelatinosa en días húmedos. Forma asociaciones micorrícicas fundamentales con los árboles nativos del bosque austral.',
    }),
    (['cyttaria darwinii'], {
        'comun': 'Digüeñe',
        'cientifico': 'Cyttaria darwinii',
        'habitat': 'Parásito específico de árboles nativos Nothofagus (especialmente coigüe y ñirre) en el sur de Chile y Patagonia.',
        'conservacion': 'No evaluado (NE)',
        'dato': 'Descrito tras el viaje de Charles Darwin por Tierra del Fuego, forma cuerpos esféricos de color blanco amarillento con hoyuelos como una pelota de golf. Es parte tradicional de la recolección estacional del sur.',
    }),
    (['entoloma necopinatum'], {
        'comun': 'Entoloma azul',
        'cientifico': 'Entoloma necopinatum',
        'habitat': 'Suelos y hojarasca de bosques templados nativos del sur de Chile.',
        'conservacion': 'No evaluado (NE)',
        'dato': 'Delicado hongo nativo de llamativo tono azul grisáceo a añil, muy apreciado por los fotógrafos de funga en el bosque valdiviano. Su aparición breve tras las lluvias otoñales anuncia la mayor actividad fúngica del año.',
    }),
    (['lactarius deliciosus'], {
        'comun': 'Níscalo',
        'cientifico': 'Lactarius deliciosus',
        'habitat': 'Especie introducida en Chile, abundante bajo plantaciones de pino (Pinus radiata) en el centro y sur.',
        'conservacion': 'Especie introducida / No evaluado (NE)',
        'dato': 'Al cortarse exuda un látex de color zanahoria intenso que con el tiempo toma tonos verdosos, rasgo clave para identificarlo. Es uno de los hongos comestibles más recolectados del centro-sur en otoño.',
    }),
    (['mycena cyanocephala'], {
        'comun': 'Mycena azul',
        'cientifico': 'Mycena cyanocephala',
        'habitat': 'Madera muerta y hojarasca húmeda de bosques templados nativos del sur de Chile.',
        'conservacion': 'No evaluado (NE)',
        'dato': 'Diminuto hongo nativo con forma de campana de un intenso azul turquesa. Cumple una función esencial descomponiendo ramitas y madera caída para reciclar nutrientes en el suelo del bosque.',
    }),
    (['mycena rubella'], {
        'comun': 'Mycena rubella',
        'cientifico': 'Mycena rubella',
        'habitat': 'Bosques húmedos y madera en descomposición del sur de Chile (bosque valdiviano).',
        'conservacion': 'No evaluado (NE)',
        'dato': 'Pequeño hongo delicado de tonos rosados a rojizos translúcidos que crece en grupos sobre troncos húmedos. Contribuye activamente a la degradación de madera en el bosque templado.',
    }),
    (['mycena subulifera'], {
        'comun': 'Mycena subulifera',
        'cientifico': 'Mycena subulifera',
        'habitat': 'Ramitas caídas y hojarasca de bosques templados nativos del sur de Chile.',
        'conservacion': 'No evaluado (NE)',
        'dato': 'Especie nativa diminuta y traslúcida de sombrero acampanado, típica del suelo húmedo del bosque austral durante el otoño.',
    }),
    (['hongo ostra'], {
        'comun': 'Hongo ostra',
        'cientifico': 'Pleurotus ostreatus',
        'habitat': 'Troncos y madera muerta en zonas templadas; ampliamente cultivado y presente en Chile.',
        'conservacion': 'No evaluado (NE)',
        'dato': 'Crece en racimos superpuestos con sombreros en forma de abanico sobre troncos muertos. Además de descomponer madera, es capaz de capturar nematodos microscópicos para obtener nitrógeno.',
    }),
]


def detectar_especie(producto):
    cat = _norm(producto.categoria.nombre if producto.categoria else '')
    nom = _norm(producto.nombre)

    # Regla 2: Excluir libros, guías, accesorios birding, casas anideras
    if any(ex in cat for ex in ['libro', 'guia', 'accesorios', 'anidera']):
        return None, 'categoria_excluida'

    # Regla 4: Productos con dos especies combinadas
    if 'hued-hued y changle' in nom or 'ranita de darwin y cortinarius' in nom:
        return None, 'doble_especie'

    # Regla 2: Excluir genéricos y otras especies fuera de ave/mamífero/hongo
    genericos_y_otros = [
        'hongos de colores', 'hongos pixel', 'hongos psicodelicos', 'hongos azules',
        'hongos magenta', 'variedad de hongos', 'hongo chico', 'hongos amarillo',
        'hongos rojo', 'hongos 1', 'hongos 2', 'hongos 3', 'hongos 4', 'hongos 5', 'hongos 6',
        'aves playeras', 'passerines', 'buhos', 'buho beige', 'buho plisado',
        'animales marinos', 'loros y guacamayos', 'ballenas', 'puffin',
        'pin gaviota', 'pin mycena', 'pin amanita', 'pin siskin',
        'picaflor', 'garzas y flores', 'garza y flores', 'pins crocs-bamers flamencos',
        'copihue', 'polythysana', 'mariposa monarca', 'tortuga verde', 'cachanando',
        'pin pinguino azul marino', 'scrunchie pinguino azul marino', 'scrunchie pinguinos',
    ]
    # Evitar falsos positivos genéricos
    if nom == 'test' or any(g in nom for g in genericos_y_otros):
        return None, 'generico_o_fuera_alcance'

    # Caso especial Pin Amanita galactica vs Amanita muscaria
    if 'amanita' in nom and 'muscaria' not in nom:
        return None, 'generico_o_fuera_alcance'

    # Caso especial Scrunchie pingüinos genérico (sin especie)
    if 'pinguino' in nom and 'humboldt' not in nom and 'magallanes' not in nom and 'rey' not in nom:
        return None, 'generico_o_fuera_alcance'

    # Buscar coincidencia exacta con nuestro diccionario aprobado
    for keywords, ficha in ESPECIES_CATALOGO:
        for kw in keywords:
            if kw in nom:
                return ficha, 'match'

    return None, 'sin_coincidencia'


class Command(BaseCommand):
    help = (
        "Puebla los campos de Ficha de Especie / Dato Curioso para productos "
        "que correspondan a una especie identificable de ave, mamífero u hongo."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Muestra vista previa sin modificar la base de datos (por defecto si no se pasa --apply).',
        )
        parser.add_argument(
            '--apply',
            action='store_true',
            help='Guarda los cambios en la base de datos.',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Sobrescribe incluso productos que ya tienen ficha de especie completa.',
        )

    def handle(self, *args, **options):
        apply_changes = options['apply']
        dry_run = options['dry_run'] or not apply_changes
        force = options['force']

        qs = Producto.objects.select_related('categoria').all().order_by('categoria__nombre', 'nombre')

        por_actualizar = []
        protegidos = []
        doble_especie = []
        excluidos = Counter()
        especies_usadas = set()

        for prod in qs:
            ya_completa = bool(
                prod.tiene_ficha_especie
                and (prod.especie_nombre_comun or '').strip()
                and (prod.especie_nombre_cientifico or '').strip()
            )
            if not force and ya_completa:
                protegidos.append(prod)
                continue

            ficha, motivo = detectar_especie(prod)
            if motivo == 'doble_especie':
                doble_especie.append(prod)
                continue
            if not ficha:
                excluidos[motivo] += 1
                continue

            especies_usadas.add(f"{ficha['comun']} ({ficha['cientifico']})")
            por_actualizar.append((prod, ficha))

        modo = 'DRY-RUN (sin cambios en BD)' if dry_run else 'APPLY (guardado en BD)'
        self.stdout.write(self.style.MIGRATE_HEADING(f"\n=== {modo} ==="))
        self.stdout.write(f"Total evaluados: {qs.count()}")
        self.stdout.write(f"Productos a poblar: {len(por_actualizar)} ({len(especies_usadas)} especies únicas)")
        self.stdout.write(f"Protegidos (ficha ya completa): {len(protegidos)}")
        self.stdout.write(f"Omitidos por doble especie: {len(doble_especie)}")
        for mot, cnt in sorted(excluidos.items()):
            self.stdout.write(f"Excluidos ({mot}): {cnt}")

        if doble_especie:
            self.stdout.write(self.style.WARNING("\nProductos con dos especies (decisión manual):"))
            for p in doble_especie:
                self.stdout.write(f"  - [{p.id}] {p.nombre}")

        if por_actualizar:
            self.stdout.write("\nMuestra de productos a poblar (primeros 10):")
            for p, f in por_actualizar[:10]:
                self.stdout.write(f"  - [{p.id}] {p.nombre} -> {f['comun']} ({f['cientifico']}) | {f['conservacion']}")

        if not dry_run and por_actualizar:
            with transaction.atomic():
                for prod, ficha in por_actualizar:
                    prod.tiene_ficha_especie = True
                    prod.especie_nombre_comun = ficha['comun']
                    prod.especie_nombre_cientifico = ficha['cientifico']
                    prod.especie_habitat = ficha['habitat']
                    prod.especie_estado_conservacion = ficha['conservacion']
                    prod.especie_dato_curioso = ficha['dato']
                    prod.save(update_fields=[
                        'tiene_ficha_especie',
                        'especie_nombre_comun',
                        'especie_nombre_cientifico',
                        'especie_habitat',
                        'especie_estado_conservacion',
                        'especie_dato_curioso',
                    ])
            self.stdout.write(self.style.SUCCESS(f"\n✅ Se poblaron {len(por_actualizar)} productos con ficha de especie."))
        elif dry_run:
            self.stdout.write(self.style.NOTICE("\nModo --dry-run activo: no se modificó la BD. Usa --apply para guardar."))
