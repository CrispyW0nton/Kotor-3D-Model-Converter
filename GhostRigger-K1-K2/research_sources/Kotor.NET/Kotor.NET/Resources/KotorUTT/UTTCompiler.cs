using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Common;
using Kotor.NET.Common.Conversation;
using Kotor.NET.Common.Data;
using Kotor.NET.Formats.KotorGFF;

namespace Kotor.NET.Resources.KotorUTT
{
    public class UTTCompiler : IGFFDecompiler<UTT>
    {
        private GFF _gff;

        public UTTCompiler(GFF gff)
        {
            _gff = gff;
        }

        public UTT Decompile()
        {
            var utt = new UTT
            {
                Tag = _gff.Root.GetString("Tag", ""),
                TemplateResRef = _gff.Root.GetResRef("TemplateResRef", new()),
                LocalizedName = _gff.Root.GetLocalizedString("LocalizedName", new()),
                AutoRemoveKey = _gff.Root.GetUInt8("AutoRemoveKey", 0),
                Faction = _gff.Root.GetUInt32("Faction", 0),
                Cursor = _gff.Root.GetUInt8("Cursor", 0),
                HighlightHeight = _gff.Root.GetSingle("HighlightHeight", 0.0f),
                KeyName = _gff.Root.GetString("KeyName", ""),
                LoadScreenID = _gff.Root.GetUInt16("LoadScreenID", 0),
                PortraitId = _gff.Root.GetUInt16("PortraitId", 0),
                Type = _gff.Root.GetInt32("Type", 0),
                TrapDetectable = _gff.Root.GetUInt8("TrapDetectable", 0),
                TrapDetectDC = _gff.Root.GetUInt8("TrapDetectDC", 0),
                TrapDisarmable = _gff.Root.GetUInt8("TrapDisarmable", 0),
                DisarmDC = _gff.Root.GetUInt8("DisarmDC", 0),
                TrapFlag = _gff.Root.GetUInt8("TrapFlag", 0),
                TrapOneShot = _gff.Root.GetUInt8("TrapOneShot", 0),
                TrapType = _gff.Root.GetUInt8("TrapType", 0),
                OnDisarm = _gff.Root.GetResRef("OnDisarm", new()),
                OnTrapTriggered = _gff.Root.GetResRef("OnTrapTriggered", new()),
                OnClick = _gff.Root.GetResRef("OnClick", new()),
                ScriptHeartbeat = _gff.Root.GetResRef("ScriptHeartbeat", new()),
                ScriptOnEnter = _gff.Root.GetResRef("ScriptOnEnter", new()),
                ScriptOnExit = _gff.Root.GetResRef("ScriptOnExit", new()),
                ScriptUserDefine = _gff.Root.GetResRef("ScriptUserDefine", new()),
                PaletteID = _gff.Root.GetUInt8("PaletteID", 0),
                Comment = _gff.Root.GetString("Comment", ""),
                Portrait = _gff.Root.GetResRef("Portrait", new()),
                LinkedTo = _gff.Root.GetString("LinkedTo", ""),
                PartyRequired = _gff.Root.GetUInt8("PartyRequired", 0),
                LinkedToFlags = _gff.Root.GetUInt8("LinkedToFlags", 0),
                LinkedToModule = _gff.Root.GetResRef("LinkedToModule", new())
            };

            return utt;
        }
    }

}
