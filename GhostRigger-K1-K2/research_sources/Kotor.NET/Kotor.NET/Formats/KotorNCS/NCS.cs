using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace Kotor.NET.Formats.KotorNCS
{
    public class NCS
    {
        public List<NCSInstruction> Instructions { get; set; } = new();

        public void Add(NCSInstruction instruction)
        {
            Instructions.Add(instruction);
        }
    }

    public abstract class NCSInstruction
    {
        public abstract InstructionBytecode Instruction { get; }
        public abstract InstructionQualifier Qualifier { get; }
        public virtual object[] Args { get; } = new object[0];
        public virtual NCSInstruction? JumpTo { get; } = null;

        public class NOP : NCSInstruction
        {
            public override InstructionBytecode Instruction => InstructionBytecode.NOP;
            public override InstructionQualifier Qualifier => 0x00;
        }

        public class CPDOWNSP : NCSInstruction
        {
            public override InstructionBytecode Instruction => InstructionBytecode.CPDOWNSP;
            public override InstructionQualifier Qualifier => (InstructionQualifier)0x01;
            public override object[] Args => new object[] { Offset, Size };
            public override NCSInstruction? JumpTo => null;

            public int Offset { get; set; }
            public ushort Size { get; set; }
        }

        public class CPTOPSP : NCSInstruction
        {
            public override InstructionBytecode Instruction => InstructionBytecode.CPTOPSP;
            public override InstructionQualifier Qualifier => (InstructionQualifier)0x01;
            public override object[] Args => new object[] { Offset, Size };
            public override NCSInstruction? JumpTo => null;

            public int Offset { get; set; }
            public ushort Size { get; set; }
        }

        public class CPDOWNBP : NCSInstruction
        {
            public override InstructionBytecode Instruction => InstructionBytecode.CPDOWNBP;
            public override InstructionQualifier Qualifier => (InstructionQualifier)0x01;
            public override object[] Args => new object[] { Offset, Size };
            public override NCSInstruction? JumpTo => null;

            public int Offset { get; set; }
            public ushort Size { get; set; }
        }

        public class CPTOPBP : NCSInstruction
        {
            public override InstructionBytecode Instruction => InstructionBytecode.CPTOPBP;
            public override InstructionQualifier Qualifier => (InstructionQualifier)0x01;
            public override object[] Args => new object[] { Offset, Size };
            public override NCSInstruction? JumpTo => null;

            public int Offset { get; set; }
            public ushort Size { get; set; }
        }

        public class ACTION : NCSInstruction
        {
            public override InstructionBytecode Instruction => InstructionBytecode.ACTION;
            public override InstructionQualifier Qualifier => (InstructionQualifier)0x00;
            public override object[] Args => new object[] { RoutineID, ArgCount };

            public ushort RoutineID { get; set; }
            public byte ArgCount { get; set; }
        }

        public class MOVSP : NCSInstruction
        {
            public override InstructionBytecode Instruction => InstructionBytecode.MOVSP;
            public override InstructionQualifier Qualifier => (InstructionQualifier)0x00;
            public override object[] Args => new object[] { Offset };

            public int Offset { get; set; }
        }

        public class DESTRUCT : NCSInstruction
        {
            public override InstructionBytecode Instruction => InstructionBytecode.DESTRUCT;
            public override InstructionQualifier Qualifier => (InstructionQualifier)0x01;
            public override object[] Args => new object[] { SizeToRemove, OffsetToSkip, SizeToSkip };

            public int SizeToRemove { get; set; }
            public int OffsetToSkip { get; set; }
            public int SizeToSkip { get; set; }

        }

        public class RETN : NCSInstruction
        {
            public override InstructionBytecode Instruction => InstructionBytecode.RETN;
            public override InstructionQualifier Qualifier => (InstructionQualifier)0x00;
        }

        public class SAVEBP : NCSInstruction
        {
            public override InstructionBytecode Instruction => InstructionBytecode.SAVEBP;
            public override InstructionQualifier Qualifier => (InstructionQualifier)0x00;
        }

        public class RESTOREBP : NCSInstruction
        {
            public override InstructionBytecode Instruction => InstructionBytecode.RESTOREBP;
            public override InstructionQualifier Qualifier => (InstructionQualifier)0x00;
        }

        public class STORESTATE : NCSInstruction
        {
            public override InstructionBytecode Instruction => InstructionBytecode.STORESTATE;
            public override InstructionQualifier Qualifier => (InstructionQualifier)0x10;
            public override object[] Args => new object[] { GlobalSize, LocalSize };

            public int GlobalSize { get; set; }
            public int LocalSize { get; set; }
        }

        //

        public class JMP : NCSInstruction
        {
            public override InstructionBytecode Instruction => InstructionBytecode.JMP;
            public override InstructionQualifier Qualifier => (InstructionQualifier)0x00;
            public override NCSInstruction JumpTo => Target;
            public NCSInstruction Target { get; set; }
        }

        public class JSR : NCSInstruction
        {
            public override InstructionBytecode Instruction => InstructionBytecode.JSR;
            public override InstructionQualifier Qualifier => (InstructionQualifier)0x00;
            public override NCSInstruction JumpTo => Target;
            public NCSInstruction Target { get; set; }
        }

        public class JZ : NCSInstruction
        {
            public override InstructionBytecode Instruction => InstructionBytecode.JZ;
            public override InstructionQualifier Qualifier => (InstructionQualifier)0x00;
            public override NCSInstruction JumpTo => Target;
            public NCSInstruction Target { get; set; }
        }

        public class JNZ : NCSInstruction
        {
            public override InstructionBytecode Instruction => InstructionBytecode.JNZ;
            public override InstructionQualifier Qualifier => (InstructionQualifier)0x00;
            public override NCSInstruction JumpTo => Target;
            public NCSInstruction Target { get; set; }
        }

        //

        public class DECISP : NCSInstruction
        {
            public override InstructionBytecode Instruction => InstructionBytecode.DECxSP;
            public override InstructionQualifier Qualifier => InstructionQualifier.INT;
            public override object[] Args => new object[] { Offset };

            public int Offset { get; set; }
        }
        
        public class INCISP : NCSInstruction
        {
            public override InstructionBytecode Instruction => InstructionBytecode.INCxSP;
            public override InstructionQualifier Qualifier => InstructionQualifier.INT;
            public override object[] Args => new object[] { Offset };

            public int Offset { get; set; }
        }

        public class DECIBP : NCSInstruction
        {
            public override InstructionBytecode Instruction => InstructionBytecode.DECxBP;
            public override InstructionQualifier Qualifier => InstructionQualifier.INT;
            public override object[] Args => new object[] { Offset };

            public int Offset { get; set; }
        }
        
        public class INCIBP : NCSInstruction
        {
            public override InstructionBytecode Instruction => InstructionBytecode.INCxBP;
            public override InstructionQualifier Qualifier => InstructionQualifier.INT;
            public override object[] Args => new object[] { Offset };

            public int Offset { get; set; }
        }

        //

        public class LOGANDII : NCSInstruction
        {
            public override InstructionBytecode Instruction => InstructionBytecode.LOGANDxx;
            public override InstructionQualifier Qualifier => InstructionQualifier.INT_INT;
        }

        public class LOGORII : NCSInstruction
        {
            public override InstructionBytecode Instruction => InstructionBytecode.LOGORxx;
            public override InstructionQualifier Qualifier => InstructionQualifier.INT_INT;
        }

        public class INCORII : NCSInstruction
        {
            public override InstructionBytecode Instruction => InstructionBytecode.INCORxx;
            public override InstructionQualifier Qualifier => InstructionQualifier.INT_INT;
        }

        public class EXCORII : NCSInstruction
        {
            public override InstructionBytecode Instruction => InstructionBytecode.EXCORxx;
            public override InstructionQualifier Qualifier => InstructionQualifier.INT_INT;
        }

        public class BOOLANDII : NCSInstruction
        {
            public override InstructionBytecode Instruction => InstructionBytecode.BOOLANDxx;
            public override InstructionQualifier Qualifier => InstructionQualifier.INT_INT;
        }

        public class EQUALII : NCSInstruction
        {
            public override InstructionBytecode Instruction => InstructionBytecode.EQUALxx;
            public override InstructionQualifier Qualifier => InstructionQualifier.INT_INT;
        }

        public class EQUALFF : NCSInstruction
        {
            public override InstructionBytecode Instruction => InstructionBytecode.EQUALxx;
            public override InstructionQualifier Qualifier => InstructionQualifier.FLOAT_FLOAT;
        }

        public class EQUALSS : NCSInstruction
        {
            public override InstructionBytecode Instruction => InstructionBytecode.EQUALxx;
            public override InstructionQualifier Qualifier => InstructionQualifier.STRING_STRING;
        }

        public class EQUALOO : NCSInstruction
        {
            public override InstructionBytecode Instruction => InstructionBytecode.EQUALxx;
            public override InstructionQualifier Qualifier => InstructionQualifier.OBJECT_OBJECT;
        }

        public class EQUALEFFEFF : NCSInstruction
        {
            public override InstructionBytecode Instruction => InstructionBytecode.EQUALxx;
            public override InstructionQualifier Qualifier => InstructionQualifier.EFFECT_EFFECT;
        }

        public class EQUALEVTEVT : NCSInstruction
        {
            public override InstructionBytecode Instruction => InstructionBytecode.EQUALxx;
            public override InstructionQualifier Qualifier => InstructionQualifier.EVENT_EVENT;
        }

        public class EQUALLOCLOC : NCSInstruction
        {
            public override InstructionBytecode Instruction => InstructionBytecode.EQUALxx;
            public override InstructionQualifier Qualifier => InstructionQualifier.LOCATION_LOCATION;
        }

        public class EQUALTALTAL : NCSInstruction
        {
            public override InstructionBytecode Instruction => InstructionBytecode.EQUALxx;
            public override InstructionQualifier Qualifier => InstructionQualifier.TALENT_TALENT;
        }

        //

        public class NEQUALII : NCSInstruction
        {
            public override InstructionBytecode Instruction => InstructionBytecode.NEQUALxx;
            public override InstructionQualifier Qualifier => InstructionQualifier.INT_INT;
        }

        public class NEQUALFF : NCSInstruction
        {
            public override InstructionBytecode Instruction => InstructionBytecode.NEQUALxx;
            public override InstructionQualifier Qualifier => InstructionQualifier.FLOAT_FLOAT;
        }

        public class NEQUALSS : NCSInstruction
        {
            public override InstructionBytecode Instruction => InstructionBytecode.NEQUALxx;
            public override InstructionQualifier Qualifier => InstructionQualifier.STRING_STRING;
        }

        public class NEQUALOO : NCSInstruction
        {
            public override InstructionBytecode Instruction => InstructionBytecode.NEQUALxx;
            public override InstructionQualifier Qualifier => InstructionQualifier.OBJECT_OBJECT;
        }

        public class NEQUALEFFEFF : NCSInstruction
        {
            public override InstructionBytecode Instruction => InstructionBytecode.NEQUALxx;
            public override InstructionQualifier Qualifier => InstructionQualifier.EFFECT_EFFECT;
        }

        public class NEQUALEVTEVT : NCSInstruction
        {
            public override InstructionBytecode Instruction => InstructionBytecode.NEQUALxx;
            public override InstructionQualifier Qualifier => InstructionQualifier.EVENT_EVENT;
        }

        public class NEQUALLOCLOC : NCSInstruction
        {
            public override InstructionBytecode Instruction => InstructionBytecode.NEQUALxx;
            public override InstructionQualifier Qualifier => InstructionQualifier.LOCATION_LOCATION;
        }

        public class NEQUALTALTAL : NCSInstruction
        {
            public override InstructionBytecode Instruction => InstructionBytecode.NEQUALxx;
            public override InstructionQualifier Qualifier => InstructionQualifier.TALENT_TALENT;
        }

        //

        public class EQUALTT : NCSInstruction
        {
            public override InstructionBytecode Instruction => InstructionBytecode.EQUALxx;
            public override InstructionQualifier Qualifier => InstructionQualifier.STRUCT_STRUCT;
            public override object[] Args => new object[] { Size }; 

            public ushort Size { get; set; }
        }

        public class NEQUALTT : NCSInstruction
        {
            public override InstructionBytecode Instruction => InstructionBytecode.NEQUALxx;
            public override InstructionQualifier Qualifier => InstructionQualifier.STRUCT_STRUCT;
            public override object[] Args => new object[] { Size }; 

            public ushort Size { get; set; }
        }

        //

        public class GEQII : NCSInstruction
        {
            public override InstructionBytecode Instruction => InstructionBytecode.GEQxx;
            public override InstructionQualifier Qualifier => InstructionQualifier.INT_INT;
        }

        public class GEQFF : NCSInstruction
        {
            public override InstructionBytecode Instruction => InstructionBytecode.GEQxx;
            public override InstructionQualifier Qualifier => InstructionQualifier.FLOAT_FLOAT;
        }

        public class GTII : NCSInstruction
        {
            public override InstructionBytecode Instruction => InstructionBytecode.GTxx;
            public override InstructionQualifier Qualifier => InstructionQualifier.INT_INT;
        }

        public class GTFF : NCSInstruction
        {
            public override InstructionBytecode Instruction => InstructionBytecode.GTxx;
            public override InstructionQualifier Qualifier => InstructionQualifier.FLOAT_FLOAT;
        }

        public class LTII : NCSInstruction
        {
            public override InstructionBytecode Instruction => InstructionBytecode.LTxx;
            public override InstructionQualifier Qualifier => InstructionQualifier.INT_INT;
        }

        public class LTFF : NCSInstruction
        {
            public override InstructionBytecode Instruction => InstructionBytecode.LTxx;
            public override InstructionQualifier Qualifier => InstructionQualifier.FLOAT_FLOAT;
        }

        public class LEQII : NCSInstruction
        {
            public override InstructionBytecode Instruction => InstructionBytecode.LEQxx;
            public override InstructionQualifier Qualifier => InstructionQualifier.INT_INT;
        }

        public class LEQFF : NCSInstruction
        {
            public override InstructionBytecode Instruction => InstructionBytecode.LEQxx;
            public override InstructionQualifier Qualifier => InstructionQualifier.FLOAT_FLOAT;
        }

        public class SHLEFTII : NCSInstruction
        {
            public override InstructionBytecode Instruction => InstructionBytecode.SHLEFTxx;
            public override InstructionQualifier Qualifier => InstructionQualifier.INT_INT;
        }

        public class SHRIGHTII : NCSInstruction
        {
            public override InstructionBytecode Instruction => InstructionBytecode.SHRIGHTxx;
            public override InstructionQualifier Qualifier => InstructionQualifier.INT_INT;
        }

        public class USHRIGHTII : NCSInstruction
        {
            public override InstructionBytecode Instruction => InstructionBytecode.USHRIGHTxx;
            public override InstructionQualifier Qualifier => InstructionQualifier.INT_INT;
        }

        //

        public class ADDII : NCSInstruction
        {
            public override InstructionBytecode Instruction => InstructionBytecode.ADDxx;
            public override InstructionQualifier Qualifier => InstructionQualifier.INT_INT;
        }

        public class ADDIF : NCSInstruction
        {
            public override InstructionBytecode Instruction => InstructionBytecode.ADDxx;
            public override InstructionQualifier Qualifier => InstructionQualifier.INT_FLOAT;
        }

        public class ADDFI : NCSInstruction
        {
            public override InstructionBytecode Instruction => InstructionBytecode.ADDxx;
            public override InstructionQualifier Qualifier => InstructionQualifier.FLOAT_INT;
        }

        public class ADDFF : NCSInstruction
        {
            public override InstructionBytecode Instruction => InstructionBytecode.ADDxx;
            public override InstructionQualifier Qualifier => InstructionQualifier.FLOAT_FLOAT;
        }

        public class ADDSS : NCSInstruction
        {
            public override InstructionBytecode Instruction => InstructionBytecode.ADDxx;
            public override InstructionQualifier Qualifier => InstructionQualifier.STRING_STRING;
        }

        public class ADDVV : NCSInstruction
        {
            public override InstructionBytecode Instruction => InstructionBytecode.ADDxx;
            public override InstructionQualifier Qualifier => InstructionQualifier.VECTOR_VECTOR;
        }

        //

        public class SUBII : NCSInstruction
        {
            public override InstructionBytecode Instruction => InstructionBytecode.SUBxx;
            public override InstructionQualifier Qualifier => InstructionQualifier.INT_INT;
        }

        public class SUBIF : NCSInstruction
        {
            public override InstructionBytecode Instruction => InstructionBytecode.SUBxx;
            public override InstructionQualifier Qualifier => InstructionQualifier.INT_FLOAT;
        }

        public class SUBFI : NCSInstruction
        {
            public override InstructionBytecode Instruction => InstructionBytecode.SUBxx;
            public override InstructionQualifier Qualifier => InstructionQualifier.FLOAT_INT;
        }

        public class SUBFF : NCSInstruction
        {
            public override InstructionBytecode Instruction => InstructionBytecode.SUBxx;
            public override InstructionQualifier Qualifier => InstructionQualifier.FLOAT_FLOAT;
        }

        public class SUBVV : NCSInstruction
        {
            public override InstructionBytecode Instruction => InstructionBytecode.SUBxx;
            public override InstructionQualifier Qualifier => InstructionQualifier.VECTOR_VECTOR;
        }

        //

        public class MULII : NCSInstruction
        {
            public override InstructionBytecode Instruction => InstructionBytecode.MULxx;
            public override InstructionQualifier Qualifier => InstructionQualifier.INT_INT;
        }

        public class MULIF : NCSInstruction
        {
            public override InstructionBytecode Instruction => InstructionBytecode.MULxx;
            public override InstructionQualifier Qualifier => InstructionQualifier.INT_FLOAT;
        }

        public class MULFI : NCSInstruction
        {
            public override InstructionBytecode Instruction => InstructionBytecode.MULxx;
            public override InstructionQualifier Qualifier => InstructionQualifier.FLOAT_INT;
        }

        public class MULFF : NCSInstruction
        {
            public override InstructionBytecode Instruction => InstructionBytecode.MULxx;
            public override InstructionQualifier Qualifier => InstructionQualifier.FLOAT_FLOAT;
        }

        public class MULFV : NCSInstruction
        {
            public override InstructionBytecode Instruction => InstructionBytecode.MULxx;
            public override InstructionQualifier Qualifier => InstructionQualifier.FLOAT_VECTOR;
        }

        public class MULVF : NCSInstruction
        {
            public override InstructionBytecode Instruction => InstructionBytecode.MULxx;
            public override InstructionQualifier Qualifier => InstructionQualifier.VECTOR_FLOAT;
        }
        

        //

        public class DIVII : NCSInstruction
        {
            public override InstructionBytecode Instruction => InstructionBytecode.DIVxx;
            public override InstructionQualifier Qualifier => InstructionQualifier.INT_INT;
        }

        public class DIVIF : NCSInstruction
        {
            public override InstructionBytecode Instruction => InstructionBytecode.DIVxx;
            public override InstructionQualifier Qualifier => InstructionQualifier.INT_FLOAT;
        }

        public class DIVFI : NCSInstruction
        {
            public override InstructionBytecode Instruction => InstructionBytecode.DIVxx;
            public override InstructionQualifier Qualifier => InstructionQualifier.FLOAT_INT;
        }

        public class DIVFF : NCSInstruction
        {
            public override InstructionBytecode Instruction => InstructionBytecode.DIVxx;
            public override InstructionQualifier Qualifier => InstructionQualifier.FLOAT_FLOAT;
        }

        public class DIVFV : NCSInstruction
        {
            public override InstructionBytecode Instruction => InstructionBytecode.DIVxx;
            public override InstructionQualifier Qualifier => InstructionQualifier.FLOAT_VECTOR;
        }

        public class DIVVF : NCSInstruction
        {
            public override InstructionBytecode Instruction => InstructionBytecode.DIVxx;
            public override InstructionQualifier Qualifier => InstructionQualifier.VECTOR_FLOAT;
        }

        //

        public class MODII : NCSInstruction
        {
            public override InstructionBytecode Instruction => InstructionBytecode.MODxx;
            public override InstructionQualifier Qualifier => InstructionQualifier.INT_INT;
        }

        public class NEGI : NCSInstruction
        {
            public override InstructionBytecode Instruction => InstructionBytecode.NEGx;
            public override InstructionQualifier Qualifier => InstructionQualifier.INT;
        }

        public class NEGF : NCSInstruction
        {
            public override InstructionBytecode Instruction => InstructionBytecode.NEGx;
            public override InstructionQualifier Qualifier => InstructionQualifier.FLOAT;
        }

        public class COMPI : NCSInstruction
        {
            public override InstructionBytecode Instruction => InstructionBytecode.COMPx;
            public override InstructionQualifier Qualifier => InstructionQualifier.INT;
        }

        public class NOTI : NCSInstruction
        {
            public override InstructionBytecode Instruction => InstructionBytecode.NOTx;
            public override InstructionQualifier Qualifier => InstructionQualifier.INT;
        }

        //

        public class RSADDI : NCSInstruction
        {
            public override InstructionBytecode Instruction => InstructionBytecode.RSADDx;
            public override InstructionQualifier Qualifier => InstructionQualifier.INT;
        }

        public class RSADDF : NCSInstruction
        {
            public override InstructionBytecode Instruction => InstructionBytecode.RSADDx;
            public override InstructionQualifier Qualifier => InstructionQualifier.FLOAT;
        }

        public class RSADDO : NCSInstruction
        {
            public override InstructionBytecode Instruction => InstructionBytecode.RSADDx;
            public override InstructionQualifier Qualifier => InstructionQualifier.OBJECT;
        }

        public class RSADDS : NCSInstruction
        {
            public override InstructionBytecode Instruction => InstructionBytecode.RSADDx;
            public override InstructionQualifier Qualifier => InstructionQualifier.STRING;
        }

        public class RSADDEFF : NCSInstruction
        {
            public override InstructionBytecode Instruction => InstructionBytecode.RSADDx;
            public override InstructionQualifier Qualifier => InstructionQualifier.EFFECT;
        }

        public class RSADDEVT : NCSInstruction
        {
            public override InstructionBytecode Instruction => InstructionBytecode.RSADDx;
            public override InstructionQualifier Qualifier => InstructionQualifier.EVENT;
        }

        public class RSADDLOC : NCSInstruction
        {
            public override InstructionBytecode Instruction => InstructionBytecode.RSADDx;
            public override InstructionQualifier Qualifier => InstructionQualifier.LOCATION;
        }

        public class RSADDTAL : NCSInstruction
        {
            public override InstructionBytecode Instruction => InstructionBytecode.RSADDx;
            public override InstructionQualifier Qualifier => InstructionQualifier.TALENT;
        }

        //

        public class CONSTI : NCSInstruction
        {
            public override InstructionBytecode Instruction => InstructionBytecode.CPDOWNSP;
            public override InstructionQualifier Qualifier => InstructionQualifier.INT;
            public override object[] Args => new object[] { Value };

            public int Value { get; set; }

            public CONSTI(int value)
            {
                Value = value;
            }
        }

        public class CONSTF : NCSInstruction
        {
            public override InstructionBytecode Instruction => InstructionBytecode.CPDOWNSP;
            public override InstructionQualifier Qualifier => InstructionQualifier.INT;
            public override object[] Args => new object[] { Value };

            public float Value { get; set; }

            public CONSTF(float value)
            {
                Value = value;
            }
        }

        public class CONSTO : NCSInstruction
        {
            public override InstructionBytecode Instruction => InstructionBytecode.CPDOWNSP;
            public override InstructionQualifier Qualifier => InstructionQualifier.INT;
            public override object[] Args => new object[] { Value };

            public ushort Value { get; set; }

            public CONSTO(ushort value)
            {
                Value = value;
            }
        }

        public class CONSTS : NCSInstruction
        {
            public override InstructionBytecode Instruction => InstructionBytecode.CPDOWNSP;
            public override InstructionQualifier Qualifier => InstructionQualifier.INT;
            public override object[] Args => new object[] { (ushort)Value.Length, Value };

            public string Value { get; set; } = "";

            public CONSTS(string value)
            {
                Value = value;
            }
        }
    }

    //public class NCSInstructionType
    //{
    //    public int Instruction { get; }
    //    public int Qualifier { get; }

    //    public NCSInstructionType(int instruction, int qualifier)
    //    {
    //        Instruction = instruction;
    //        Qualifier = qualifier;
    //    }
    //}

    public enum InstructionBytecode
    {
        NOP = 0x2D,
        CPDOWNSP = 0x01,
        RSADDx = 0x02,
        CPTOPSP = 0x03,
        CONSTx = 0x04,
        ACTION = 0x05,
        LOGANDxx = 0x06,
        LOGORxx = 0x07,
        INCORxx = 0x08,
        EXCORxx = 0x09,
        BOOLANDxx = 0x0A,
        EQUALxx = 0x0B,
        NEQUALxx = 0x0C,
        GEQxx = 0x0D,
        GTxx = 0x0E,
        LTxx = 0x0F,
        LEQxx = 0x10,
        SHLEFTxx = 0x11,
        SHRIGHTxx = 0x12,
        USHRIGHTxx = 0x13,
        ADDxx = 0x14,
        SUBxx = 0x15,
        MULxx = 0x16,
        DIVxx = 0x17,
        MODxx = 0x18,
        NEGx = 0x19,
        COMPx = 0x1A,
        MOVSP = 0x1B,
        JMP = 0x1D,
        JSR = 0x1E,
        JZ = 0x1F,
        RETN = 0x20,
        DESTRUCT = 0x21,
        NOTx = 0x22,
        DECxSP = 0x23,
        INCxSP = 0x24,
        CPDOWNBP = 0x26,
        CPTOPBP = 0x27,
        DECxBP = 0x28,
        INCxBP = 0x29,
        JNZ = 0x25,
        SAVEBP = 0x2A,
        RESTOREBP = 0x2B,
        STORESTATE = 0x2C,
        NOP2 = 0x2D,
    }

    public enum InstructionQualifier
    {
        INT = 0x03,
        FLOAT = 0x04,
        STRING = 0x05,
        OBJECT = 0x06,
        EFFECT = 0x10,
        EVENT = 0x11,
        LOCATION = 0x12,
        TALENT = 0x13,
        INT_INT =  0x20,
        FLOAT_FLOAT = 0x21,
        OBJECT_OBJECT = 0x22,
        STRING_STRING = 0x23,
        STRUCT_STRUCT = 0x24,
        INT_FLOAT = 0x25,
        FLOAT_INT = 0x26,
        EFFECT_EFFECT = 0x30,
        EVENT_EVENT = 0x31,
        LOCATION_LOCATION = 0x32,
        TALENT_TALENT = 0x33,
        VECTOR_VECTOR = 0x3A,
        VECTOR_FLOAT = 0x3B,
        FLOAT_VECTOR = 0x3C,
    }
}
