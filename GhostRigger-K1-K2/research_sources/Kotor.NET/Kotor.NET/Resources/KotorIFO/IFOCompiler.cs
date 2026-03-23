using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Common;
using Kotor.NET.Common.Conversation;
using Kotor.NET.Common.Data;
using Kotor.NET.Formats.KotorGFF;
using Kotor.NET.Formats.KotorMDL;

namespace Kotor.NET.Resources.KotorIFO
{
    public class IFOCompiler : IGFFDecompiler<IFO>
    {
        private GFF _gff;

        public IFOCompiler(GFF gff)
        {
            _gff = gff;
        }

        public IFO Decompile()
        {
            var ifo = new IFO
            {
                Mod_ID = _gff.Root.GetBinary("Mod_ID"),
                Mod_Creator_ID = _gff.Root.GetInt32("Mod_Creator_ID", 0),
                Mod_Version = _gff.Root.GetUInt32("Mod_Version", 0),
                Mod_VO_ID = _gff.Root.GetString("Mod_VO_ID", ""),
                Expansion_Pack = _gff.Root.GetUInt16("Expansion_Pack", 0),
                Mod_Name = _gff.Root.GetLocalizedString("Mod_Name", new LocalizedString()),
                Mod_Tag = _gff.Root.GetString("Mod_Tag", ""),
                Mod_Hak = _gff.Root.GetString("Mod_Hak", ""),
                Mod_Description = _gff.Root.GetLocalizedString("Mod_Description", new LocalizedString()),
                Mod_IsSaveGame = _gff.Root.GetUInt8("Mod_IsSaveGame", 0),
                Mod_Entry_Area = _gff.Root.GetResRef("Mod_Entry_Area", new ResRef()),
                Mod_Entry_X = _gff.Root.GetSingle("Mod_Entry_X", 0),
                Mod_Entry_Y = _gff.Root.GetSingle("Mod_Entry_Y", 0),
                Mod_Entry_Z = _gff.Root.GetSingle("Mod_Entry_Z", 0),
                Mod_Entry_Dir_X = _gff.Root.GetSingle("Mod_Entry_Dir_X", 0),
                Mod_Entry_Dir_Y = _gff.Root.GetSingle("Mod_Entry_Dir_Y", 0),
                Mod_DawnHour = _gff.Root.GetUInt8("Mod_DawnHour", 0),
                Mod_DuskHour = _gff.Root.GetUInt8("Mod_DuskHour", 0),
                Mod_MinPerHour = _gff.Root.GetUInt8("Mod_MinPerHour", 0),
                Mod_StartMonth = _gff.Root.GetUInt8("Mod_StartMonth", 0),
                Mod_StartDay = _gff.Root.GetUInt8("Mod_StartDay", 0),
                Mod_StartHour = _gff.Root.GetUInt8("Mod_StartHour", 0),
                Mod_StartYear = _gff.Root.GetUInt32("Mod_StartYear", 0),
                Mod_XPScale = _gff.Root.GetUInt8("Mod_XPScale", 0),
                Mod_OnHeartbeat = _gff.Root.GetResRef("Mod_OnHeartbeat", new ResRef()),
                Mod_OnModLoad = _gff.Root.GetResRef("Mod_OnModLoad", new ResRef()),
                Mod_OnModStart = _gff.Root.GetResRef("Mod_OnModStart", new ResRef()),
                Mod_OnClientEntr = _gff.Root.GetResRef("Mod_OnClientEntr", new ResRef()),
                Mod_OnClientLeav = _gff.Root.GetResRef("Mod_OnClientLeav", new ResRef()),
                Mod_OnActvtItem = _gff.Root.GetResRef("Mod_OnActvtItem", new ResRef()),
                Mod_OnAcquirItem = _gff.Root.GetResRef("Mod_OnAcquirItem", new ResRef()),
                Mod_OnUsrDefined = _gff.Root.GetResRef("Mod_OnUsrDefined", new ResRef()),
                Mod_OnUnAqreItem = _gff.Root.GetResRef("Mod_OnUnAqreItem", new ResRef()),
                Mod_OnPlrDeath = _gff.Root.GetResRef("Mod_OnPlrDeath", new ResRef()),
                Mod_OnPlrDying = _gff.Root.GetResRef("Mod_OnPlrDying", new ResRef()),
                Mod_OnPlrLvlUp = _gff.Root.GetResRef("Mod_OnPlrLvlUp", new ResRef()),
                Mod_OnSpawnBtnDn = _gff.Root.GetResRef("Mod_OnSpawnBtnDn", new ResRef()),
                Mod_OnPlrRest = _gff.Root.GetResRef("Mod_OnPlrRest", new ResRef()),
                Mod_StartMovie = _gff.Root.GetResRef("Mod_StartMovie", new ResRef()),

                Mod_Area_list = _gff.Root.GetList("Mod_Area_list", new())
                    .Select(gffArea => gffArea.GetResRef("Area_Name"))
                    .ToList(),
            };

            return ifo;
        }
    }
}
