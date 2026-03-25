using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace Kotor.NET.Common.Data
{
    public class ResourceType
    {
        public static ResourceType UNIDENTIFIED = new ResourceType(0, "", "Unidentified");
        public static ResourceType BMP = new ResourceType(1, "bmp", "Images");
        public static ResourceType TGA = new ResourceType(3, "tga", "Textures");
        public static ResourceType WAV = new ResourceType(4, "wav", "Audio");
        public static ResourceType PLT = new ResourceType(6, "plt", "Others");
        public static ResourceType INI = new ResourceType(7, "ini", "Others");
        public static ResourceType TXT = new ResourceType(10, "txt", "Others");
        public static ResourceType MDL = new ResourceType(2002, "mdl", "Models");
        public static ResourceType NSS = new ResourceType(2009, "nss", "Scripts");
        public static ResourceType NCS = new ResourceType(2010, "ncs", "Scripts");
        public static ResourceType MOD = new ResourceType(2011, "mod", "Modules");
        public static ResourceType ARE = new ResourceType(2012, "are", "Module Data");
        public static ResourceType SET = new ResourceType(2013, "set", "Unused");
        public static ResourceType IFO = new ResourceType(2014, "ifo", "Module Data");
        public static ResourceType BIC = new ResourceType(2015, "bic", "Creature");
        public static ResourceType WOK = new ResourceType(2016, "wok", "Models");
        public static ResourceType TWODA = new ResourceType(2017, "2da", "2D Arrays");
        public static ResourceType TLK = new ResourceType(2018, "tlk", "Talk Tables");
        public static ResourceType TXI = new ResourceType(2022, "txi", "Textures");
        public static ResourceType GIT = new ResourceType(2023, "git", "Module Data");
        public static ResourceType BTI = new ResourceType(2024, "bti", "Items");
        public static ResourceType UTI = new ResourceType(2025, "uti", "Items");
        public static ResourceType BTC = new ResourceType(2026, "btc", "Creatures");
        public static ResourceType UTC = new ResourceType(2027, "utc", "Creatures");
        public static ResourceType DLG = new ResourceType(2029, "dlg", "Dialogs");
        public static ResourceType ITP = new ResourceType(2030, "itp", "Palettes");
        public static ResourceType UTT = new ResourceType(2032, "utt", "Triggers");
        public static ResourceType DDS = new ResourceType(2033, "dds", "Textures");
        public static ResourceType UTS = new ResourceType(2035, "uts", "Sounds");
        public static ResourceType LTR = new ResourceType(2036, "ltr", "Others");
        public static ResourceType GFF = new ResourceType(2037, "gff", "Others");
        public static ResourceType FAC = new ResourceType(2038, "fac", "Factions");
        public static ResourceType UTE = new ResourceType(2040, "ute", "Encounters");
        public static ResourceType UTD = new ResourceType(2042, "utd", "Doors");
        public static ResourceType UTP = new ResourceType(2044, "utp", "Placeables");
        public static ResourceType DFT = new ResourceType(2045, "dft", "Others");
        public static ResourceType GIC = new ResourceType(2046, "gic", "Module Data");
        public static ResourceType GUI = new ResourceType(2047, "gui", "GUIs");
        public static ResourceType UTM = new ResourceType(2051, "utm", "Merchants");
        public static ResourceType DWK = new ResourceType(2052, "dwk", "Models");
        public static ResourceType PWK = new ResourceType(2053, "pwk", "Models");
        public static ResourceType JRL = new ResourceType(2056, "jrl", "Journals");
        public static ResourceType UTW = new ResourceType(2058, "utw", "Waypoints");
        public static ResourceType SSF = new ResourceType(2060, "ssf", "Soundsets");
        public static ResourceType NDB = new ResourceType(2064, "ndb", "Others");
        public static ResourceType PTM = new ResourceType(2065, "ptm", "Others");
        public static ResourceType PTT = new ResourceType(2066, "ptt", "Others");
        public static ResourceType JPG = new ResourceType(2076, "jpg", "Images");
        public static ResourceType PNG = new ResourceType(2110, "png", "Images");
        public static ResourceType LYT = new ResourceType(3000, "lyt", "Module Data");
        public static ResourceType VIS = new ResourceType(3001, "vis", "Module Data");
        public static ResourceType RIM = new ResourceType(3002, "rim", "Modules");
        public static ResourceType PTH = new ResourceType(3003, "pth", "Paths");
        public static ResourceType LIP = new ResourceType(3004, "lip", "LIPs");
        public static ResourceType TPC = new ResourceType(3007, "tpc", "Textures");
        public static ResourceType MDX = new ResourceType(3008, "mdx", "Models");
        public static ResourceType ERF = new ResourceType(9997, "erf", "Modules");
        public static ResourceType MP3 = new ResourceType(25014, "mp3", "Audio");

        public static ResourceType[] ResourceTypes = new[]
        {
            BMP, TGA, WAV, PLT, INI, TXT, MDL, NSS, NCS, MOD, ARE, SET, IFO, WOK,
            TWODA, TLK, TXI, GIT, BTI, UTI, BTC, UTC, DLG, ITP ,UTT, DDS, UTS, LTR,
            GFF, FAC, UTE, UTD, UTP, DFT, GIC, GUI, UTM, DWK, PWK, JRL, UTW, SSF,
            NDB, PTM, PTT, JPG, PNG, LYT, VIS, RIM, PTH, LIP, TPC, MDX, ERF, MP3
        };

        public int ID { get; set; }
        public string Extension { get; set; }
        public string Category { get; set; }

        internal ResourceType(int id, string extension, string category)
        {
            ID = id;
            Extension = extension;
            Category = category;
        }

        public static ResourceType ByID(int id)
        {
            return ResourceTypes.SingleOrDefault(x => x.ID == id) ?? UNIDENTIFIED;
        }

        public static ResourceType ByExtension(string extension)
        {
            return ResourceTypes.Single(x => x.Extension == extension);
        }

        public override string ToString()
        {
            return Extension.ToUpper();
        }
    }
}
