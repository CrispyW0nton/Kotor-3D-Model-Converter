using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace Kotor.NET.Scripting
{
    public class SymbolTable
    {
        public Dictionary<string, StructDefinition> Structs { get; set; } = new();
        public Dictionary<string, InstructionPlaceholder> Functions { get; set; } = new();
        public Dictionary<string, GlobalVariable> GlobalVariables { get; set; } = new();

        public void DeclareGlobalVariable(string identifier, DataType dataType)
        {
            if (GlobalVariables.ContainsKey(identifier))
            {
                throw new ArgumentException("A symbol with that identifier already exists.");
            }

            GlobalVariables.Add(identifier, new GlobalVariable(identifier, dataType));
        }
    }

    public class InstructionPlaceholder
    {

    }

    public class GlobalVariable
    {
        public string Identifier { get; set; }
        public DataType DataType { get; set; }

        public GlobalVariable(string identifier, DataType dataType)
        {
            Identifier = identifier;
            DataType = dataType;
        }
    }

    public class StructDefinition
    {
        public string Identifier { get; set; }

        public StructDefinition(string identifier)
        {
            Identifier = identifier;
        }
    }

    public class DataType
    {
        public static readonly DataType Int = new("int");
        public static readonly DataType Float = new("float");
        public static readonly DataType String = new("string");
        public static readonly DataType Vector = new("vector");
        public static readonly DataType Event = new("event");
        public static readonly DataType Effect = new("effect");
        public static readonly DataType ItemProperty = new("itemproperty");
        public static readonly DataType Talent = new("talent");
        public static readonly DataType Location = new("location");
        public static readonly DataType Void = new("void");
        public static readonly DataType Action = new("action");
        public static readonly DataType Object = new("object");

        public string Type { get => _type; }

        private string _type;

        private DataType(string identifier)
        {
            _type = identifier;
        }

        public override string ToString()
        {
            return Type;
        }
    }
}
