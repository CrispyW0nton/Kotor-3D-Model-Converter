using System;
using System.Collections.Generic;
using System.Linq;
using System.Numerics;
using System.Text;
using System.Threading.Tasks;
using IniParser.Model;
using Kotor.NET.Common.Conversation;
using Kotor.NET.Patcher.Exceptions;
using Kotor.NET.Extensions;
using Kotor.NET.Formats.KotorGFF;
using Kotor.NET.Patcher.Modifiers.ForGFF;
using Kotor.NET.Patcher.Modifiers.ForGFF.Values;
using Microsoft.VisualBasic.FileIO;

namespace Kotor.NET.Patcher.Parsers.LegacyINI
{
    public class GFFSectionParser
    {
        private IniData _ini;
        private KeyDataCollection _section;

        private Dictionary<string, GFFFieldType> tslpatcherFieldTypeToInternalFieldTypes = new Dictionary<string, GFFFieldType>
        {
            { "Byte", GFFFieldType.UInt8 },
            { "Char", GFFFieldType.Int8 },
            { "Word", GFFFieldType.UInt16 },
            { "Short", GFFFieldType.Int16 },
            { "DWORD", GFFFieldType.UInt32 },
            { "Int", GFFFieldType.Int32 },
            { "Float", GFFFieldType.Single },
            { "Int64", GFFFieldType.Int64 },
            { "Double", GFFFieldType.Double },
            { "ExoString", GFFFieldType.String },
            { "ResRef", GFFFieldType.ResRef },
            { "ExoLocString", GFFFieldType.LocalizedString },
            { "Orientation", GFFFieldType.Vector4 },
            { "Position", GFFFieldType.Vector3 },
            { "Struct", GFFFieldType.Struct },
            { "List", GFFFieldType.List },
        };

        public GFFSectionParser(IniData ini, KeyDataCollection section)
        {
            _ini = ini;
            _section = section;
        }

        public List<IModifier<GFF>> Parse()
        {
            var modifiers = new List<IModifier<GFF>>();

            foreach (var section in _section)
            {
                var modifierPair = _ini[section.Value];

                if (section.KeyName.StartsWith("AddField"))
                {
                    var modifier = ParseAddFieldSection(modifierPair);
                    modifiers.Add(modifier);
                }
                else
                {
                    var modifier = ParseModifyFieldSection(section);
                    modifiers.Add(modifier);
                }
            }

            return modifiers;
        }

        public IModifier<GFF> ParseModifyFieldSection(KeyData section)
        {
            var nodes = section.KeyName.Split("\\", StringSplitOptions.RemoveEmptyEntries);
            var path = nodes.Take(nodes.Count() - 1).ToArray();
            var value = section.Value;

            var label = nodes.Last();
            var directive = "";
            var hasDirective = label.Contains("(") && label.Contains(")");
            if (hasDirective)
            {
                var start = label.IndexOf("(");
                var end = label.IndexOf(")");
                directive = label.Substring(start + 1, end - start - 1);
                label = label.Substring(0, start);
            }

            return new ModifyFieldGFFModifier(label, directive, path, value);
        }

        public IGFFModifier ParseAddFieldSection(KeyDataCollection section)
        {
            var fieldType = GetFieldType(section);
            var value = GetFieldValue(section, fieldType);
            var path = GetFieldPath(section);
            var label = GetFieldLabel(section);
            var toStoreInMemory = GetToStoreInMemory(section);
            var subfields = GetFieldSubFields(section);

            IGFFModifier modifier = null;

            if (fieldType == GFFFieldType.Struct && label == "")
            {
                modifier = new AddStructToList(value, path, toStoreInMemory, subfields);
            }
            else
            {
                modifier = new AddFieldToStructGFFModifier(label, value, fieldType, path, toStoreInMemory, subfields);
            }

            return modifier;
        }

        private GFFFieldType GetFieldType(KeyDataCollection section)
        {
            if (section.ContainsKey("FieldType"))
            {
                var fieldTypeText = section["FieldType"];

                if (tslpatcherFieldTypeToInternalFieldTypes.ContainsKey(fieldTypeText))
                {
                    return tslpatcherFieldTypeToInternalFieldTypes[fieldTypeText];
                }
                else
                {
                    throw new PatchingParserException("Unknown field type was specified for AddField.");
                }
            }
            else
            {
                throw new PatchingParserException("No field type was specified for AddField.");
            }
        }

        private object GetFieldValue(KeyDataCollection section, GFFFieldType fieldType)
        {
            var valueText = section.FirstOrDefault(x => x.KeyName == "Value")?.Value ?? "";
            object? value = null;
            
            if (fieldType == GFFFieldType.UInt8)
            {
                value = (valueText.IsUInt8()) ? Convert.ToByte(valueText) : throw new Exception("Value was not a UInt8.");
            }
            else if (fieldType == GFFFieldType.Int8)
            {
                value = (valueText.IsInt8()) ? Convert.ToSByte(valueText) : throw new Exception("Value was not a Int8.");
            }
            else if (fieldType == GFFFieldType.UInt16)
            {
                value = (valueText.IsUInt16()) ? Convert.ToUInt16(valueText) : throw new Exception("Value was not a UInt16.");
            }
            else if (fieldType == GFFFieldType.Int16)
            {
                value = (valueText.IsInt16()) ? Convert.ToInt16(valueText) : throw new Exception("Value was not a Int16.");
            }
            else if (fieldType == GFFFieldType.UInt32)
            {
                value = (valueText.IsUInt32()) ? Convert.ToUInt32(valueText) : throw new Exception("Value was not a UInt32.");
            }
            else if (fieldType == GFFFieldType.Int32)
            {
                value = (valueText.IsInt32()) ? Convert.ToInt32(valueText) : throw new Exception("Value was not a Int32.");
            }
            else if (fieldType == GFFFieldType.UInt64)
            {
                value = (valueText.IsUInt64()) ? Convert.ToUInt64(valueText) : throw new Exception("Value was not a UInt64.");
            }
            else if (fieldType == GFFFieldType.Int64)
            {
                value = (valueText.IsInt64()) ? Convert.ToInt64(valueText) : throw new Exception("Value was not a Int64.");
            }
            else if (fieldType == GFFFieldType.Single)
            {
                value = (valueText.IsSingle()) ? Convert.ToSingle(valueText) : throw new Exception("Value was not a Single.");
            }
            else if (fieldType == GFFFieldType.Double)
            {
                value = (valueText.IsDouble()) ? Convert.ToDouble(valueText) : throw new Exception("Value was not a Double.");
            }
            else if (fieldType == GFFFieldType.ResRef)
            {
                value = (valueText.Length <= 16) ? valueText : throw new Exception("ResRef cannot exceed 16 characters.");
            }
            else if (fieldType == GFFFieldType.Vector3)
            {
                value = ParseVector3(valueText);
            }
            else if (fieldType == GFFFieldType.Vector4)
            {
                value = ParseVector4(valueText);
            }
            else if (fieldType == GFFFieldType.LocalizedString)
            {
                var strRefText = section.FirstOrDefault(x => x.KeyName == "StrRef")?.Value ?? "";
                var langIDsText = section.Where(x => x.KeyName.StartsWith("lang")).ToList();

                if (strRefText.IsInt32() && langIDsText.All(x => x.KeyName.Replace("lang", "").IsInt32()))
                {
                    var locstring = new LocalizedString();
                    locstring.StringRef = Convert.ToInt32(strRefText);
                    langIDsText.ForEach(x => locstring.Set(Convert.ToInt32(x.KeyName.Replace("lang", "")), x.Value));
                    value = locstring;
                }
                else
                {
                    throw new PatchingParserException("StrRef or a Language ID was not a integer.");
                }
            }
            else if (fieldType == GFFFieldType.Struct)
            {
                var idText = section.FirstOrDefault(x => x.KeyName == "TypeId")?.Value ?? "";

                if (idText.IsUInt32())
                {
                    var id = Convert.ToUInt32(value);
                    value = new GFFStruct(id);
                }
                else
                {
                    throw new PatchingParserException("TypeId for Struct was not an integer.");
                }
            }
            else if (fieldType == GFFFieldType.List)
            {
                value = new GFFList();
            }
            else
            {

            }

            return value;
        }

        private string GetFieldPath(KeyDataCollection section)
        {
            return section.FirstOrDefault(x => x.KeyName == "Path")?.Value ?? "";
        }

        private string GetFieldLabel(KeyDataCollection section)
        {
            return section.FirstOrDefault(x => x.KeyName == "Label")?.Value ?? "";
        }

        private Dictionary<int, IValue> GetToStoreInMemory(KeyDataCollection section)
        {
            return new(); // TODO
        }

        private List<IGFFModifier> GetFieldSubFields(KeyDataCollection section)
        {
            var list = new List<IGFFModifier>();

            foreach (var pair in section.Where(x => x.KeyName.StartsWith("AddField")))
            {
                var modifier = ParseAddFieldSection(_ini[pair.Value]);
                list.Add(modifier);
            }

            return list;
        }

        private Vector3 ParseVector3(string vectorText)
        {
            var floats = vectorText.Split("|").Where(x => x.IsSingle()).Select(x => Convert.ToSingle(x)).ToArray();

            if (floats.Length == 3)
            {
                return new Vector3(floats[0], floats[1], floats[2]);
            }
            else
            {
                throw new PatchingParserException("Vector3 was incorrectly formatted.");
            }
        }

        private Vector4 ParseVector4(string vectorText)
        {
            var floats = vectorText.Split("|").Where(x => x.IsSingle()).Select(x => Convert.ToSingle(x)).ToArray();

            if (floats.Length == 4)
            {
                return new Vector4(floats[0], floats[1], floats[2], floats[3]);
            }
            else
            {
                throw new PatchingParserException("Vector4 was incorrectly formatted.");
            }
        }
    }
}
