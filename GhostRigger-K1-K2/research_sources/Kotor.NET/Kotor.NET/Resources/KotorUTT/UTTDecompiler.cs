using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Common;
using Kotor.NET.Formats.KotorGFF;

namespace Kotor.NET.Resources.KotorUTT
{
    public class UTTDecompiler : IGFFCompiler
    {
        private UTT _utt;

        public UTTDecompiler(UTT utt)
        {
            _utt = utt;
        }

        public GFF CompileGFF()
        {
            var gff = new GFF();

            gff.Root.SetString("Tag", _utt.Tag);
            gff.Root.SetResRef("TemplateResRef", _utt.TemplateResRef);
            gff.Root.SetLocalizedString("LocalizedName", _utt.LocalizedName);
            gff.Root.SetUInt8("AutoRemoveKey", _utt.AutoRemoveKey);
            gff.Root.SetUInt32("Faction", _utt.Faction);
            gff.Root.SetUInt8("Cursor", _utt.Cursor);
            gff.Root.SetSingle("HighlightHeight", _utt.HighlightHeight);
            gff.Root.SetString("KeyName", _utt.KeyName);
            gff.Root.SetUInt16("LoadScreenID", _utt.LoadScreenID);
            gff.Root.SetUInt16("PortraitId", _utt.PortraitId);
            gff.Root.SetInt32("Type", _utt.Type);
            gff.Root.SetUInt8("TrapDetectable", _utt.TrapDetectable);
            gff.Root.SetUInt8("TrapDetectDC", _utt.TrapDetectDC);
            gff.Root.SetUInt8("TrapDisarmable", _utt.TrapDisarmable);
            gff.Root.SetUInt8("DisarmDC", _utt.DisarmDC);
            gff.Root.SetUInt8("TrapFlag", _utt.TrapFlag);
            gff.Root.SetUInt8("TrapOneShot", _utt.TrapOneShot);
            gff.Root.SetUInt8("TrapType", _utt.TrapType);
            gff.Root.SetResRef("OnDisarm", _utt.OnDisarm);
            gff.Root.SetResRef("OnTrapTriggered", _utt.OnTrapTriggered);
            gff.Root.SetResRef("OnClick", _utt.OnClick);
            gff.Root.SetResRef("ScriptHeartbeat", _utt.ScriptHeartbeat);
            gff.Root.SetResRef("ScriptOnEnter", _utt.ScriptOnEnter);
            gff.Root.SetResRef("ScriptOnExit", _utt.ScriptOnExit);
            gff.Root.SetResRef("ScriptUserDefine", _utt.ScriptUserDefine);
            gff.Root.SetUInt8("PaletteID", _utt.PaletteID);
            gff.Root.SetString("Comment", _utt.Comment);
            gff.Root.SetResRef("Portrait", _utt.Portrait);
            gff.Root.SetString("LinkedTo", _utt.LinkedTo);
            gff.Root.SetUInt8("PartyRequired", _utt.PartyRequired);
            gff.Root.SetUInt8("LinkedToFlags", _utt.LinkedToFlags);
            gff.Root.SetResRef("LinkedToModule", _utt.LinkedToModule);

            return gff;
        }
    }
}
