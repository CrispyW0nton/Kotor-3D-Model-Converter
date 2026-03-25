using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Common;
using Kotor.NET.Formats.KotorGFF;

namespace Kotor.NET.Resources.KotorIFO
{
    public class IFODecompiler : IGFFCompiler
    {
        private IFO _ifo;

        public IFODecompiler(IFO ifo)
        {
            _ifo = ifo;
        }

        public GFF CompileGFF()
        {
            var gff = new GFF();

            gff.Root.SetBinary("Mod_ID", _ifo.Mod_ID);
            gff.Root.SetInt32("Mod_Creator_ID", _ifo.Mod_Creator_ID);
            gff.Root.SetUInt32("Mod_Version", _ifo.Mod_Version);
            gff.Root.SetString("Mod_VO_ID", _ifo.Mod_VO_ID);
            gff.Root.SetUInt16("Expansion_Pack", _ifo.Expansion_Pack);
            gff.Root.SetLocalizedString("Mod_Name", _ifo.Mod_Name);
            gff.Root.SetString("Mod_Tag", _ifo.Mod_Tag);
            gff.Root.SetString("Mod_Hak", _ifo.Mod_Hak);
            gff.Root.SetLocalizedString("Mod_Description", _ifo.Mod_Description);
            gff.Root.SetUInt8("Mod_IsSaveGame", _ifo.Mod_IsSaveGame);
            gff.Root.SetResRef("Mod_Entry_Area", _ifo.Mod_Entry_Area);
            gff.Root.SetSingle("Mod_Entry_X", _ifo.Mod_Entry_X);
            gff.Root.SetSingle("Mod_Entry_Y", _ifo.Mod_Entry_Y);
            gff.Root.SetSingle("Mod_Entry_Z", _ifo.Mod_Entry_Z);
            gff.Root.SetSingle("Mod_Entry_Dir_X", _ifo.Mod_Entry_Dir_X);
            gff.Root.SetSingle("Mod_Entry_Dir_Y", _ifo.Mod_Entry_Dir_Y);

            var expanList = gff.Root.SetList("Mod_Expan_List", new());

            gff.Root.SetUInt8("Mod_DawnHour", _ifo.Mod_DawnHour);
            gff.Root.SetUInt8("Mod_DuskHour", _ifo.Mod_DuskHour);
            gff.Root.SetUInt8("Mod_MinPerHour", _ifo.Mod_MinPerHour);
            gff.Root.SetUInt8("Mod_StartMonth", _ifo.Mod_StartMonth);
            gff.Root.SetUInt8("Mod_StartDay", _ifo.Mod_StartDay);
            gff.Root.SetUInt8("Mod_StartHour", _ifo.Mod_StartHour);
            gff.Root.SetUInt32("Mod_StartYear", _ifo.Mod_StartYear);
            gff.Root.SetUInt8("Mod_XPScale", _ifo.Mod_XPScale);
            gff.Root.SetResRef("Mod_OnHeartbeat", _ifo.Mod_OnHeartbeat);
            gff.Root.SetResRef("Mod_OnModLoad", _ifo.Mod_OnModLoad);
            gff.Root.SetResRef("Mod_OnModStart", _ifo.Mod_OnModStart);
            gff.Root.SetResRef("Mod_OnClientEntr", _ifo.Mod_OnClientEntr);
            gff.Root.SetResRef("Mod_OnClientLeav", _ifo.Mod_OnClientLeav);
            gff.Root.SetResRef("Mod_OnActvtItem", _ifo.Mod_OnActvtItem);
            gff.Root.SetResRef("Mod_OnAcquirItem", _ifo.Mod_OnAcquirItem);
            gff.Root.SetResRef("Mod_OnUsrDefined", _ifo.Mod_OnUsrDefined);
            gff.Root.SetResRef("Mod_OnUnAqreItem", _ifo.Mod_OnUnAqreItem);
            gff.Root.SetResRef("Mod_OnPlrDeath", _ifo.Mod_OnPlrDeath);
            gff.Root.SetResRef("Mod_OnPlrDying", _ifo.Mod_OnPlrDying);
            gff.Root.SetResRef("Mod_OnPlrLvlUp", _ifo.Mod_OnPlrLvlUp);
            gff.Root.SetResRef("Mod_OnSpawnBtnDn", _ifo.Mod_OnSpawnBtnDn);
            gff.Root.SetResRef("Mod_OnPlrRest", _ifo.Mod_OnPlrRest);
            gff.Root.SetResRef("Mod_StartMovie", _ifo.Mod_StartMovie);

            var areaList = gff.Root.SetList("Mod_Area_list", new());
            foreach (var item in _ifo.Mod_Area_list)
            {
                areaList.Add().SetResRef("Area_Name", item);
            }

            return gff;
        }
    }
}
