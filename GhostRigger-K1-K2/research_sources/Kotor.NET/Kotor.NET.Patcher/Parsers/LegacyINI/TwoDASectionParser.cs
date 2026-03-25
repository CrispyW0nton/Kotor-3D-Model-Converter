using IniParser.Model;
using Kotor.NET.Formats.Kotor2DA;
using Kotor.NET.Patcher.Modifiers.For2DA.Targets;
using Kotor.NET.Patcher.Modifiers.For2DA.Values;
using Kotor.NET.Patcher.Modifiers.For2DA;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using static System.Runtime.InteropServices.JavaScript.JSType;
using Kotor.NET.Patcher.Exceptions;

namespace Kotor.NET.Patcher.Parsers.LegacyINI
{
    public class TwoDASectionParser
    {
        private IniData _ini;
        private KeyDataCollection _section;

        public TwoDASectionParser(IniData ini, KeyDataCollection section)
        {
            _ini = ini;
            _section = section;
        }

        public List<IModifier<TwoDA>> Parse()
        {
            var modifiers = new List<IModifier<TwoDA>>();

            foreach (var twodaSection in _section)
            {
                var modifierPair = _ini[twodaSection.Value];

                if (twodaSection.KeyName.StartsWith("ChangeRow"))
                {
                    var modifier = ParseEditRowSection(modifierPair);
                    modifiers.Add(modifier);
                }
                else if (twodaSection.KeyName.StartsWith("AddRow"))
                {
                    var modifier = ParseAddRowSection(modifierPair);
                    modifiers.Add(modifier);
                }
                else if (twodaSection.KeyName.StartsWith("CopyRow"))
                {
                    var modifier = ParseCopyRowSection(modifierPair);
                    modifiers.Add(modifier);
                }
                else if (twodaSection.KeyName.StartsWith("AddColumn"))
                {
                    var modifier = ParseAddColumnSection(modifierPair);
                    modifiers.Add(modifier);
                }
                else
                {
                    throw new PatchingParserException("Unrecognized 2DA modifier key.");
                }
            }

            return modifiers;
        }

        protected ChangeRow2DAModifier ParseEditRowSection(KeyDataCollection section)
        {
            ITarget target = TakeTarget(section);
            Dictionary<int, IValue> toStoreInMemory = TakeToStoreInMemory(section);
            Dictionary<string, IValue> data = TakeValues(section);
            return new(target, data, toStoreInMemory);
        }

        protected AddRow2DAModifier ParseAddRowSection(KeyDataCollection section)
        {
            string? exclusiveColumn = TakeExclusiveColumn(section);
            IValue rowLabel = TakeRowLabel(section, "RowLabel");
            Dictionary<int, IValue> toStoreInMemory = TakeToStoreInMemory(section);
            Dictionary<string, IValue> data = TakeValues(section);
            return new(exclusiveColumn, rowLabel, data, toStoreInMemory);

            //if (section.ContainsKey("I"))
            //{
            //    int rowIndex = 0;
            //    if (!int.TryParse(section["RowIndex"], out rowIndex))
            //    {
            //        throw new PatchingParserException("The row index given was not an integer.");
            //    }
            //    target = new RowIndexTarget(rowIndex);
            //    section.RemoveKey("RowIndex");
            //}
            //else if (section.ContainsKey("RowLabel"))
            //{
            //    target = new RowHeaderTarget(section["RowLabel"]);
            //    section.RemoveKey("RowIndex");
            //}
            //else if (section.ContainsKey("LabelIndex"))
            //{
            //    target = new ColumnTarget("label", section["LabelIndex"]);
            //    section.RemoveKey("RowIndex");
            //}
            //else
            //{
            //    throw new PatchingParserException("No information was given on which row to edit.");
            //}
        }

        protected CopyRow2DAModifier ParseCopyRowSection(KeyDataCollection section)
        {
            ITarget target = TakeTarget(section);
            string? exclusiveColumn = TakeExclusiveColumn(section);
            IValue rowLabel = TakeRowLabel(section, "NewRowLabel");
            Dictionary<int, IValue> toStoreInMemory = TakeToStoreInMemory(section);
            Dictionary<string, IValue> data = TakeValues(section);
            return new(target, exclusiveColumn, rowLabel, data, toStoreInMemory);
        }

        protected AddColumn2DAModifier ParseAddColumnSection(KeyDataCollection section)
        {
            var columnHeader = "";
            var defaultValue = "";
            var values = new Dictionary<ITarget, IValue>();
            var toStore = new Dictionary<int, IValue>();

            if (section.ContainsKey("ColumnLabel"))
            {
                columnHeader = section["ColumnLabel"];
                section.RemoveKey("ColumnLabel");
            }
            else
            {
                throw new PatchingParserException("No header was specified for the new column.");
            }

            if (section.ContainsKey("DefaultValue"))
            {
                defaultValue = section["DefaultValue"];
                section.RemoveKey("DefaultValue");
            }
            else
            {
                defaultValue = "";
            }

            foreach (var key in section.Select(x => x.KeyName))
            {
                var rawValue = section[key];

                if (key.StartsWith("2DAMEMORY"))
                {
                    var tokenID = 0;
                    var tokenIDString = key.Split("2DAMEMORY").Last();
                    var validTokenID = int.TryParse(tokenIDString, out tokenID);

                    if (validTokenID)
                    {
                        toStore[tokenID] = ParseAddColumnValue(rawValue, columnHeader);
                    }
                    else
                    {
                        throw new PatchingParserException("Assigned 2DAMEMORY token ID is not an integer.");
                    }
                }
                else if (key.StartsWith("I"))
                {
                    var rowIndex = 0;
                    var rowIndexString = key.Split("I").Last();
                    var validRowIndex = int.TryParse(rowIndexString, out rowIndex);

                    if (validRowIndex)
                    {
                        var target = new RowIndexTarget(rowIndex);
                        var value = ParseValue(rawValue, false);
                        values.Add(target, value);
                    }
                    else
                    {
                        throw new PatchingParserException("Assigned Row Index is not an integer.");
                    }
                }
                else if (key.StartsWith("L"))
                {
                    var rowHeader = key.Split("L").Last();

                    if (key.Length > 1)
                    {
                        var target = new RowHeaderTarget(rowHeader);
                        var value = ParseValue(rawValue, false);
                        values.Add(target, value);
                    }
                    else
                    {
                        throw new PatchingParserException("Assigned Row Header is empty.");
                    }
                }
            }

            AddColumn2DAModifier modifier = new(columnHeader, defaultValue, values, toStore);
            return modifier;
        }

        //

        protected IValue ParseValue(string text, bool columnInsteadOfConstant)
        {
            if (text.StartsWith("2DAMEMORY"))
            {
                var tokenIDString = text.Split("2DAMEMORY").Last();
                var tokenID = 0;
                var validTokenID = int.TryParse(tokenIDString, out tokenID);

                if (validTokenID)
                {
                    return new TwoDAMemoryValue(tokenID);
                }
                else
                {
                    return new ConstantValue(text);
                }
            }
            else if (text.StartsWith("StrRef"))
            {
                var tokenIDString = text.Split("StrRef").Last();
                var tokenID = 0;
                var validTokenID = int.TryParse(tokenIDString, out tokenID);

                if (validTokenID)
                {
                    return new TLKMemoryValue(tokenID);
                }
                else
                {
                    return new ConstantValue(text);
                }
            }
            else if (text.StartsWith("high()"))
            {
                return new HighestValue();
            }
            else if (text.StartsWith("RowIndex"))
            {
                return new RowIndexValue();
            }
            else if (text.StartsWith("RowLabel"))
            {
                return new RowHeaderValue();
            }
            else if (columnInsteadOfConstant)
            {
                return new CellValue(text);
            }
            else
            {
                return new ConstantValue(text);
            }
        }

        protected IValue ParseAddColumnValue(string text, string columnHeader)
        {
            if (text.StartsWith("I"))
            {
                int number;
                var isValidNumber = int.TryParse(text.Substring(1), out number);
                if (isValidNumber)
                {
                    var target = new RowIndexTarget(number);
                    return new AbsoluteCellValue(target, columnHeader);
                }
                else
                {
                    throw new PatchingParserException("Invalid row index for 2DAMEMORY.");
                }
            }
            else if (text.StartsWith("L"))
            {
                var rowLabel = text.Substring(1);
                var target = new RowHeaderTarget(rowLabel);
                return new AbsoluteCellValue(target, columnHeader);
            }
            else
            {
                throw new PatchingParserException("Trying to assign a value of unknown format to 2DAMEMORY.");
            }
        }

        //

        protected ITarget TakeTarget(KeyDataCollection section)
        {
            if (section.ContainsKey("RowIndex"))
            {
                int rowIndex = 0;
                if (!int.TryParse(section["RowIndex"], out rowIndex))
                {
                    throw new PatchingParserException("The row index given was not an integer.");
                }
                section.RemoveKey("RowIndex");
                return new RowIndexTarget(rowIndex);
            }
            else if (section.ContainsKey("RowLabel"))
            {
                var rowHeader = section["RowLabel"];
                section.RemoveKey("RowLabel");
                return new RowHeaderTarget(rowHeader);
            }
            else if (section.ContainsKey("LabelIndex"))
            {
                var labelIndex = section["LabelIndex"];
                section.RemoveKey("LabelIndex");
                return new ColumnTarget("label", labelIndex);
            }
            else
            {
                throw new PatchingParserException("No information was given on which row to edit.");
            }
        }

        protected Dictionary<int, IValue> TakeToStoreInMemory(KeyDataCollection section)
        {
            var toStoreInMemory = new Dictionary<int, IValue>();

            foreach (var pair in section.Where(x => x.KeyName.StartsWith("2DAMEMORY")))
            {
                var tokenID = 0;
                var tokenIDString = pair.KeyName.Split("2DAMEMORY").Last();
                var validTokenID = int.TryParse(tokenIDString, out tokenID);

                if (validTokenID)
                {
                    IValue value = ParseValue(pair.Value, true);
                    toStoreInMemory.Add(tokenID, value);
                }

                section.RemoveKey(pair.KeyName);
            }

            return toStoreInMemory;
        }

        protected Dictionary<string, IValue> TakeValues(KeyDataCollection section)
        {
            var values = new Dictionary<string, IValue>();

            foreach (var pair in section)
            {
                IValue value = ParseValue(pair.Value, false);
                values.Add(pair.KeyName, value);
            }

            return values;
        }

        protected string? TakeExclusiveColumn(KeyDataCollection section)
        {
            var pair = section.FirstOrDefault(x => x.KeyName == "ExclusiveColumn");
            section.RemoveKey("ExclusiveColumn");
            return pair?.Value;
        }

        protected IValue TakeRowLabel(KeyDataCollection section, string keyname)
        {
            var pair = section.FirstOrDefault(x => x.KeyName == keyname);
            section.RemoveKey(keyname);

            if (pair != null)
            {
                return new ConstantValue(pair.Value);
            }
            else
            {
                return new RowIndexValue();
            }
        }
    }
}
